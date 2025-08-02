from flask import Flask, jsonify
import snap7
from snap7 import Area
from snap7.util import set_bool, get_bool, get_int
import socket
print("🧠 Máy đang dùng IP LAN là:", socket.gethostbyname(socket.gethostname()))
app = Flask(__name__)

# Cấu hình PLC
PLC_IP = "192.168.0.5"  # 🔁 Đảm bảo IP này đúng với PLC của bạn
RACK = 0
SLOT = 1
DB_NUMBER = 11 # Data Block cho thang máy (Đảm bảo khớp với PLC của bạn, ví dụ: DB1)

# --- Địa chỉ biến trong DB11 ---
# Các biến này sẽ được ghi từ Flask xuống PLC để điều khiển
# Byte 0: Các lệnh gọi từ Cabin
BYTE_OFFSET_CABIN_CALLS = 0 # Đổi tên cho rõ ràng hơn
BIT_CABIN_FLOOR_1_CALL = 2
BIT_CABIN_FLOOR_2_CALL = 3
BIT_CABIN_FLOOR_3_CALL = 4
BIT_CABIN_FLOOR_4_CALL = 5

# Byte 4: Các lệnh gọi từ bên ngoài Cabin (Up/Down)
BYTE_OFFSET_OUTSIDE_CALL_COMMANDS = 4
BIT_FLOOR_1_UP_CALL = 0
BIT_FLOOR_2_UP_CALL = 1
BIT_FLOOR_2_DOWN_CALL = 5
BIT_FLOOR_3_UP_CALL = 2
BIT_FLOOR_3_DOWN_CALL = 4
BIT_FLOOR_4_DOWN_CALL = 3

# Word 2: Vị trí Cabin hiện tại (Đọc từ PLC)
INT_OFFSET_CABIN_POSITION_READ = 2  # DB11.DBW2 (WORD, 2 bytes)

# --- Địa chỉ biến trong M-Area cho điều khiển cửa ---
# M52.2 cho mở cửa, M52.3 cho đóng cửa
MB_OFFSET_DOOR_COMMANDS = 52 # Memory Byte 52
BIT_OPEN_DOOR_CMD = 2       # Bit 2 của Memory Byte 52 (M52.2)
BIT_CLOSE_DOOR_CMD = 3      # Bit 3 của Memory Byte 52 (M52.3)


# Tạo đối tượng PLC
client = snap7.client.Client()


def ensure_connected():
    """Đảm bảo kết nối tới PLC, kết nối lại nếu mất."""
    if not client.get_connected():
        try:
            client.connect(PLC_IP, RACK, SLOT)
            print(f"✅ Đã kết nối lại tới PLC tại {PLC_IP}")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối lại PLC: {e}")
            return False
    return True


# Hàm write_plc_bit được sửa đổi để chấp nhận loại Area (DB hoặc MK)
def write_plc_bit(area_type, byte_offset, bit_offset, value, db_num=None):
    """
    Ghi một bit cụ thể trong Data Block hoặc Memory Area của PLC.
    Đọc byte hiện tại, thay đổi bit, sau đó ghi lại byte.
    :param area_type: Loại vùng nhớ (Area.DB, Area.MK, v.v.)
    :param byte_offset: Byte offset trong vùng nhớ.
    :param bit_offset: Bit offset trong byte.
    :param value: Giá trị boolean (True/False) để ghi.
    :param db_num: Số Data Block nếu area_type là Area.DB. Bỏ qua nếu là Area.MK.
    """
    if not ensure_connected():
        raise Exception("PLC chưa kết nối.")

    try:
        # Xác định kích thước đọc (1 byte)
        read_size = 1

        # Đọc 1 byte từ địa chỉ đã cho
        if area_type == Area.DB:
            if db_num is None:
                raise ValueError("db_num phải được cung cấp cho Area.DB")
            data = client.read_area(area_type, db_num, byte_offset, read_size)
        else: # Đối với Area.MK (Memory Area)
            data = client.read_area(area_type, 0, byte_offset, read_size) # Offset 0 cho M-Area, byte_offset là địa chỉ thực

        byte_array = bytearray(data)  # Chuyển đổi sang bytearray để có thể sửa đổi

        # Đặt giá trị bit
        set_bool(byte_array, 0, bit_offset, value) # byte_array, byte_index_in_array, bit_index_in_byte, value

        # Ghi lại byte đã sửa đổi vào PLC
        if area_type == Area.DB:
            client.write_area(area_type, db_num, byte_offset, byte_array)
            print(f"Đã ghi DB{db_num}.DBX{byte_offset}.{bit_offset} = {value}")
        else: # Đối với Area.MK
            client.write_area(area_type, 0, byte_offset, byte_array) # Offset 0 cho M-Area
            print(f"Đã ghi M{byte_offset}.{bit_offset} = {value}")
    except Exception as e:
        area_str = f"DB{db_num}.DBX" if area_type == Area.DB else "M"
        print(f"Lỗi khi ghi {area_str}{byte_offset}.{bit_offset}: {e}")
        raise


def read_plc_int_value(int_offset, db_num=DB_NUMBER):
    """
    Đọc giá trị của một INT (WORD) cụ thể từ Data Block của PLC.
    INT chiếm 2 bytes.
    """
    if not ensure_connected():
        raise Exception("PLC chưa kết nối.")

    try:
        # Đọc 2 bytes từ địa chỉ đã cho (vì INT là 2 bytes)
        data = client.read_area(Area.DB, db_num, int_offset, 2)
        read_value = get_int(data, 0)  # Lấy giá trị số nguyên từ 2 bytes
        print(f"✅ Đã đọc DB{db_num}.DBW{int_offset}: Giá trị = {read_value}")
        return read_value
    except Exception as e:
        print(f"❌ Lỗi khi đọc DB{db_num}.DBW{int_offset}: {e}")
        raise


# --- Elevator Control Endpoints (Phù hợp với ứng dụng Android) ---

# Endpoint cho các nút gọi tầng bên trong Cabin
@app.route("/elevator/cabin/call/<int:floor>", methods=["GET"])
def cabin_call_floor(floor):
    try:
        if not (1 <= floor <= 4):
            return jsonify({"status": "error", "message": "Tầng không hợp lệ (1-4)."}), 400

        bit_offset = -1
        if floor == 1:
            bit_offset = BIT_CABIN_FLOOR_1_CALL
        elif floor == 2:
            bit_offset = BIT_CABIN_FLOOR_2_CALL
        elif floor == 3:
            bit_offset = BIT_CABIN_FLOOR_3_CALL
        elif floor == 4:
            bit_offset = BIT_CABIN_FLOOR_4_CALL

        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_CABIN_CALLS, bit_offset, True, DB_NUMBER)

        return jsonify({"status": "success", "message": f"Đã gọi thang máy đến tầng {floor} từ Cabin."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Endpoint cho nút Mở cửa từ Cabin
@app.route("/elevator/door/open", methods=["GET"])
def elevator_open_door():
    try:
        # Ghi vào Memory Area (M-Area)
        write_plc_bit(Area.MK, MB_OFFSET_DOOR_COMMANDS, BIT_OPEN_DOOR_CMD, True)
        return jsonify({"status": "success", "message": "Đã gửi lệnh mở cửa."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Endpoint cho nút Đóng cửa từ Cabin
@app.route("/elevator/door/close", methods=["GET"])
def elevator_close_door():
    try:
        # Ghi vào Memory Area (M-Area)
        write_plc_bit(Area.MK, MB_OFFSET_DOOR_COMMANDS, BIT_CLOSE_DOOR_CMD, True)
        return jsonify({"status": "success", "message": "Đã gửi lệnh đóng cửa."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Endpoint cho các nút gọi LÊN/XUỐNG bên ngoài Cabin
@app.route("/elevator/floor/1/up", methods=["GET"])
def floor_1_up():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_1_UP_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy LÊN từ Tầng 1."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/elevator/floor/2/up", methods=["GET"])
def floor_2_up():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_2_UP_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy LÊN từ Tầng 2."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/elevator/floor/2/down", methods=["GET"])
def floor_2_down():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_2_DOWN_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy XUỐNG từ Tầng 2."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/elevator/floor/3/up", methods=["GET"])
def floor_3_up():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_3_UP_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy LÊN từ Tầng 3."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/elevator/floor/3/down", methods=["GET"])
def floor_3_down():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_3_DOWN_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy XUỐNG từ Tầng 3."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/elevator/floor/4/down", methods=["GET"])
def floor_4_down():
    try:
        # Ghi vào Data Block (DB11)
        write_plc_bit(Area.DB, BYTE_OFFSET_OUTSIDE_CALL_COMMANDS, BIT_FLOOR_4_DOWN_CALL, True, DB_NUMBER)
        return jsonify({"status": "success", "message": "Đã gọi thang máy XUỐNG từ Tầng 4."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Endpoint để lấy vị trí Cabin hiện tại
@app.route("/status", methods=["GET"])
@app.route("/elevator/position", methods=["GET"])
def get_cabin_position():
    try:
        # Gọi hàm để đọc giá trị INT từ DB11
        position_int = read_plc_int_value(INT_OFFSET_CABIN_POSITION_READ)

        # Map giá trị int sang tên tầng
        position_text = ""
        if position_int == 0:
            position_text = "Đang di chuyển/Chưa xác định"
        elif 1 <= position_int <= 4:
            position_text = f"Tầng {position_int}"
        else:
            position_text = "Giá trị không hợp lệ"

        return jsonify({"status": "success", "position_value": position_int, "display_text": position_text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Kết nối PLC ban đầu khi server khởi động
if __name__ == "__main__":
    try:
        client.connect(PLC_IP, RACK, SLOT)
        print(f"✅ Đã kết nối tới PLC tại {PLC_IP}")
    except Exception as e:
        print(f"❌ Lỗi kết nối ban đầu tới PLC: {e}")

    app.run(host="192.168.137.1", port=5000, debug=True)
