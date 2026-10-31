"""소프트웨어 간 Modbus TCP를 표준 라이브러리 소켓으로 구현한다. 실제 PLC, 실제 네트워크 장비가 아니다."""

from decimal import Decimal, InvalidOperation, localcontext
import socket
import struct
import threading
import time

from src.recipe import is_decimal_text


UNIT_ID = 1
ADDRESS_SPACE = 16
HEADER_BYTES = 6
MIN_LENGTH = 2
MAX_LENGTH = 254

READ_COILS = 0x01
READ_DISCRETE = 0x02
READ_HOLDING = 0x03
READ_INPUT = 0x04
WRITE_COIL = 0x05
WRITE_REGISTER = 0x06
WRITE_REGISTERS = 0x10
FUNCTIONS = (READ_COILS, READ_DISCRETE, READ_HOLDING, READ_INPUT, WRITE_COIL, WRITE_REGISTER, WRITE_REGISTERS)

ILLEGAL_FUNCTION = 1
ILLEGAL_ADDRESS = 2
ILLEGAL_VALUE = 3
DEVICE_FAILURE = 4

COIL_ON = 0xFF00
COIL_OFF = 0x0000
RESET_COIL = 8
RELEASE_COIL = 9
PC_STOP_COIL = 10
HEARTBEAT_REGISTER = 0
JUDGE_REGISTER = 1
JUDGE_REGISTERS = 2
WRITABLE_COILS = (RESET_COIL, RELEASE_COIL, PC_STOP_COIL)

VALUE_SCALE = 1000
VALUE_MIN = -2147483648
VALUE_MAX = 2147483647


class ValueConversionError(ValueError):
    """측정값이 정수 천분율 32비트로 정확히 표현되지 않는다."""


class ModbusResponseError(ConnectionError):
    """응답이 요청과 맞지 않거나 연결이 끊겼다. 클라이언트는 연결을 닫는다."""


class ModbusTimeout(TimeoutError):
    """응답 제한 시간을 넘겼다."""


class ModbusException(Exception):
    """서버가 형식에 맞는 예외 응답을 돌려줬다. 연결은 유지된다."""

    def __init__(self, function, code):
        super().__init__("function 0x%02X exception %02d" % (function, code))
        self.function = function
        self.code = code


def to_words(text):
    """측정값 문자열을 상위·하위 워드로 바꾼다. 2의 보수이고 상위 워드가 앞선다."""
    if not is_decimal_text(text):
        raise ValueConversionError(str(text) + ": 소수 문자열이 아님")
    with localcontext() as context:
        context.prec = 60
        scaled = Decimal(text) * VALUE_SCALE
        if scaled != scaled.to_integral_value():
            raise ValueConversionError(text + ": 소수 셋째 자리를 넘음")
    number = int(scaled)
    if not VALUE_MIN <= number <= VALUE_MAX:
        raise ValueConversionError(text + ": 32비트 범위를 넘음")
    raw = number & 0xFFFFFFFF
    return raw >> 16, raw & 0xFFFF


def from_words(high, low):
    """워드를 부호 있는 정수로 합친다."""
    raw = high << 16 | low
    return raw - (1 << 32) if raw & 0x80000000 else raw


def restore_value(high, low):
    """워드를 소수 셋째 자리 문자열로 복원한다."""
    number = from_words(high, low)
    sign = "-" if number < 0 else ""
    whole, fraction = divmod(abs(number), VALUE_SCALE)
    return "%s%d.%03d" % (sign, whole, fraction)


class Table:
    """PLC, 모의 설비, 서버가 함께 쓰는 주소표다. 모든 접근은 lock 안에서 한다."""

    def __init__(self):
        self.lock = threading.Lock()
        self.coils = [False] * ADDRESS_SPACE
        self.discrete = [False] * ADDRESS_SPACE
        self.holding = [0] * ADDRESS_SPACE
        self.input_registers = [0] * ADDRESS_SPACE


def _words(*values):
    return struct.pack(">" + "H" * len(values), *values)


def _pack_bits(bits):
    packed = bytearray((len(bits) + 7) // 8)
    for index, bit in enumerate(bits):
        if bit:
            packed[index // 8] |= 1 << (index % 8)
    return bytes(packed)


def _unpack_bits(packed, count):
    return [bool(packed[index // 8] >> (index % 8) & 1) for index in range(count)]


def _exception(function, code):
    return bytes((function | 0x80, code))


def _read_error(pdu, limit):
    if len(pdu) != 5:
        return ILLEGAL_VALUE
    start, count = struct.unpack(">HH", pdu[1:5])
    if not 1 <= count <= limit:
        return ILLEGAL_VALUE
    if start + count > ADDRESS_SPACE:
        return ILLEGAL_ADDRESS
    return None


def _read_bits(pdu, bits):
    error = _read_error(pdu, 2000)
    if error:
        return _exception(pdu[0], error)
    start, count = struct.unpack(">HH", pdu[1:5])
    packed = _pack_bits(bits[start:start + count])
    return bytes((pdu[0], len(packed))) + packed


def _read_registers(pdu, registers):
    error = _read_error(pdu, 125)
    if error:
        return _exception(pdu[0], error)
    start, count = struct.unpack(">HH", pdu[1:5])
    return bytes((pdu[0], count * 2)) + _words(*registers[start:start + count])


def _write_coil(pdu, table):
    if len(pdu) != 5:
        return _exception(pdu[0], ILLEGAL_VALUE)
    address, value = struct.unpack(">HH", pdu[1:5])
    if value not in (COIL_ON, COIL_OFF):
        return _exception(pdu[0], ILLEGAL_VALUE)
    if address not in WRITABLE_COILS:
        return _exception(pdu[0], ILLEGAL_ADDRESS)
    table.coils[address] = value == COIL_ON
    return pdu


def _write_register(pdu, table):
    if len(pdu) != 5:
        return _exception(pdu[0], ILLEGAL_VALUE)
    address, value = struct.unpack(">HH", pdu[1:5])
    if address != HEARTBEAT_REGISTER:
        return _exception(pdu[0], ILLEGAL_ADDRESS)
    table.holding[address] = value
    return pdu


def _write_registers(pdu, table):
    if len(pdu) < 6:
        return _exception(pdu[0], ILLEGAL_VALUE)
    start, count, size = struct.unpack(">HHB", pdu[1:6])
    if len(pdu) != 6 + size or size != count * 2 or not 1 <= count <= 123:
        return _exception(pdu[0], ILLEGAL_VALUE)
    if start != JUDGE_REGISTER or count != JUDGE_REGISTERS:
        return _exception(pdu[0], ILLEGAL_ADDRESS)
    table.holding[start:start + count] = struct.unpack(">" + "H" * count, pdu[6:])
    return pdu[:5]


def handle_pdu(pdu, table):
    """요청 PDU 하나를 처리해 응답 PDU를 돌려준다. 검증이 끝나기 전에는 쓰지 않는다."""
    function = pdu[0]
    if function not in FUNCTIONS:
        return _exception(function, ILLEGAL_FUNCTION)
    try:
        with table.lock:
            if function == READ_COILS:
                return _read_bits(pdu, table.coils)
            if function == READ_DISCRETE:
                return _read_bits(pdu, table.discrete)
            if function == READ_HOLDING:
                return _read_registers(pdu, table.holding)
            if function == READ_INPUT:
                return _read_registers(pdu, table.input_registers)
            if function == WRITE_COIL:
                return _write_coil(pdu, table)
            if function == WRITE_REGISTER:
                return _write_register(pdu, table)
            return _write_registers(pdu, table)
    except Exception:
        return _exception(function, DEVICE_FAILURE)


class FrameBuffer:
    """길이 기반 수신 버퍼다. 분할·병합 수신을 모두 처리한다.

    손상을 만나도 앞의 완성 프레임은 돌려주고 damaged만 세운다. 호출자는 그 프레임을 처리한 뒤 닫는다.
    그래서 같은 바이트열의 결과가 수신 분할에 따라 달라지지 않는다.
    """

    def __init__(self):
        self.data = bytearray()
        self.damaged = False

    def feed(self, chunk):
        self.data.extend(chunk)
        frames = []
        while len(self.data) >= HEADER_BYTES:
            _, protocol, length = struct.unpack(">HHH", self.data[:HEADER_BYTES])
            if protocol != 0 or not MIN_LENGTH <= length <= MAX_LENGTH:
                self.damaged = True
                break
            total = HEADER_BYTES + length
            if len(self.data) < total:
                break
            frames.append(bytes(self.data[:total]))
            del self.data[:total]
        return frames


def respond(frame, table):
    """완성된 요청 프레임의 응답 프레임을 만든다. Unit ID가 다르면 None이다."""
    transaction, _, _, unit = struct.unpack(">HHHB", frame[:7])
    if unit != UNIT_ID:
        return None
    pdu = handle_pdu(frame[7:], table)
    return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu


class ModbusServer:
    """127.0.0.1의 임시 포트에서 연결을 하나씩 받는다."""

    def __init__(self, table):
        self.table = table
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.05)
        self.port = self.listener.getsockname()[1]
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self.stopping.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(None)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._serve(connection)

    def _serve(self, connection):
        buffer = FrameBuffer()
        while True:
            try:
                chunk = connection.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            for frame in buffer.feed(chunk):
                reply = respond(frame, self.table)
                if reply is not None:
                    try:
                        connection.sendall(reply)
                    except OSError:
                        return
            if buffer.damaged:
                return

    def close(self):
        self.stopping.set()
        self.thread.join(5)
        self.listener.close()


class ModbusClient:
    """요청을 보내고 응답을 기다린다. on_frame은 완성된 프레임을 방향·기능·16진수로 받는다."""

    def __init__(self, port, timeout=1.0, on_frame=None):
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.timeout = timeout
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buffer = FrameBuffer()
        self.transaction = 0
        self.on_frame = on_frame or (lambda direction, function, text: None)
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.socket.close()
            self.on_frame("close", 0, "")

    def _fail(self, message):
        self.close()
        raise ModbusResponseError(message)

    def _chunk(self, deadline):
        """제한 시간은 요청 하나의 마감이다. 조각마다 다시 세면 느린 응답이 통과한다."""
        remaining = deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise socket.timeout
            self.socket.settimeout(remaining)
            return self.socket.recv(4096)
        except socket.timeout as error:
            self.close()
            raise ModbusTimeout("응답 제한 시간 초과") from error
        except OSError as error:
            self.close()
            raise ModbusResponseError("수신 실패: " + str(error)) from error

    def _receive(self, deadline):
        frames = []
        while not frames:
            chunk = self._chunk(deadline)
            if not chunk:
                self._fail("연결 끊김")
            frames = self.buffer.feed(chunk)
            if self.buffer.damaged:
                self._fail("응답 MBAP 손상")
        if len(frames) > 1 or self.buffer.data:
            self._fail("요청보다 응답이 많음")
        return frames[0]

    def request(self, pdu):
        """요청 하나를 보내고 머리를 확인한 응답 PDU를 돌려준다. 예외 응답은 ModbusException이다."""
        if self.closed:
            raise ModbusResponseError("연결이 닫혔음")
        self.transaction = self.transaction % 65535 + 1
        frame = struct.pack(">HHHB", self.transaction, 0, len(pdu) + 1, UNIT_ID) + pdu
        self.on_frame("request", pdu[0], frame.hex(" "))
        deadline = time.monotonic() + self.timeout
        try:
            self.socket.settimeout(self.timeout)
            self.socket.sendall(frame)
        except socket.timeout as error:
            self.close()
            raise ModbusTimeout("응답 제한 시간 초과") from error
        except OSError as error:
            self.close()
            raise ModbusResponseError("송신 실패: " + str(error)) from error
        reply = self._receive(deadline)
        self.on_frame("response", reply[7] if len(reply) > 7 else 0, reply.hex(" "))
        transaction, _, _, unit = struct.unpack(">HHHB", reply[:7])
        body = reply[7:]
        if transaction != self.transaction:
            self._fail("트랜잭션 ID 불일치")
        if unit != UNIT_ID:
            self._fail("Unit ID 불일치")
        if not body:
            self._fail("빈 응답")
        if body[0] == pdu[0] | 0x80:
            if len(body) != 2:
                self._fail("예외 응답 길이 오류")
            raise ModbusException(pdu[0], body[1])
        if body[0] != pdu[0]:
            self._fail("기능 코드 불일치")
        return body

    def read_bits(self, function, start, count):
        body = self.request(_function_with(function, start, count))
        size = (count + 7) // 8
        if len(body) != 2 + size or body[1] != size:
            self._fail("바이트 수 불일치")
        return _unpack_bits(body[2:], count)

    def read_registers(self, function, start, count):
        body = self.request(_function_with(function, start, count))
        if len(body) != 2 + count * 2 or body[1] != count * 2:
            self._fail("바이트 수 불일치")
        return list(struct.unpack(">" + "H" * count, body[2:]))

    def _write_echo(self, pdu):
        if self.request(pdu) != pdu:
            self._fail("에코 불일치")

    def write_coil(self, address, value):
        self._write_echo(_function_with(WRITE_COIL, address, COIL_ON if value else COIL_OFF))

    def write_register(self, address, value):
        self._write_echo(_function_with(WRITE_REGISTER, address, value))

    def write_registers(self, start, values):
        head = _function_with(WRITE_REGISTERS, start, len(values))
        if self.request(head + bytes((len(values) * 2,)) + _words(*values)) != head:
            self._fail("시작 주소·수량 불일치")


def _function_with(function, first, second):
    return bytes((function,)) + _words(first, second)
