"""
pi_serial_server.py — شغّله على الـ Raspberry Pi
يستقبل HTTP POST من الـ HTML ويبعت الأمر للأردوينو عبر Serial

تشغيل:
    pip install flask flask-cors pyserial
    python pi_serial_server.py

بعدين افتح الـ HTML من أي جهاز على نفس الشبكة — هيتواصل تلقائياً

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  خريطة الأوامر (من كود الأردوينو):
    A → ketofan   (station A)
    B → brufen    (station B)
    C → cataflam  (station C)
    D → ambezim   (station D / وقوف)
    S → line tracking / رجوع للبداية
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import time
import serial
import serial.tools.list_ports
from flask import Flask, request, jsonify
from flask_cors import CORS

# ═══════════════════════════════════════════
#  CONFIG — غيّر SERIAL_PORT لو لازم
# ═══════════════════════════════════════════
SERIAL_PORT     = '/dev/ttyUSB0'   # أو /dev/ttyACM0 حسب الأردوينو
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT  = 2
SERVER_PORT     = 5050             # نفس PI_SERVER في الـ HTML

# ─────────────────────────────────────────────────────────────────
#  خريطة الدواء → حرف الأردوينو
#  ⚠️  مطابقة 100% لكود الأردوينو:
#      A=ketofan  B=brufen  C=cataflam  D=ambezim  S=line tracking
#  ملاحظة: trimed_flu مفيش له station مستقل في الأردوينو —
#           لو محتاج تضيفه اضف case جديدة في loop() بحرف زي 'E'
# ─────────────────────────────────────────────────────────────────
SERIAL_COMMANDS = {
    'ketofan'    : 'A',   # → Arduino command A (station A)
    'brufen'     : 'B',   # → Arduino command B (station B)
    'cataflam'   : 'C',   # → Arduino command C (station C)
    'ambezim'    : 'D',   # → Arduino command D (stop / station D)
    'trimed_flu' : 'A',   # ⚠️ مفيش station خاص — بيروح station A مؤقتاً
                          #    غيّره لحرف جديد لو ضفت station في الأردوينو
    'sleep'      : 'S',   # → Arduino command S (line tracking / home)
}

# ═══════════════════════════════════════════
#  SERIAL INIT
# ═══════════════════════════════════════════
ser = None

def init_serial():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT)
        time.sleep(2)  # انتظر الأردوينو يتهيأ
        print(f'[Serial] ✅  Connected: {SERIAL_PORT} @ {SERIAL_BAUDRATE}')
    except serial.SerialException as e:
        ser = None
        print(f'[Serial] ⚠️  {e}')
        print('[Serial] شغّال بدون Arduino — هيلوج الأوامر بس')

        # حاول تقترح البورت الصح
        ports = serial.tools.list_ports.comports()
        if ports:
            print('[Serial] البورتات المتاحة:')
            for p in ports:
                print(f'  {p.device}  —  {p.description}')
        else:
            print('[Serial] مفيش بورتات serial متاحة.')

def send_command(cmd: str) -> bool:
    """يبعت حرف واحد للأردوينو. يرجع True لو نجح."""
    if ser and ser.is_open:
        ser.write(cmd.encode())
        time.sleep(0.05)
        return True
    return False

# ═══════════════════════════════════════════
#  FLASK APP
# ═══════════════════════════════════════════
app = Flask(__name__)
CORS(app)  # ضروري — يسمح للـ HTML يبعت request من أي origin

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'ok'              : True,
        'serial_connected': ser is not None and ser.is_open,
        'port'            : SERIAL_PORT,
        'commands_map'    : SERIAL_COMMANDS,
    })

@app.route('/send', methods=['POST'])
def send():
    data     = request.get_json(force=True, silent=True) or {}
    cmd      = data.get('command', '').strip().upper()
    medicine = data.get('medicine', 'unknown')

    # لو الـ HTML بعت اسم الدواء بدون حرف — نحوله تلقائياً
    if not cmd:
        med_key = medicine.lower().strip().replace(' ', '_')
        cmd = SERIAL_COMMANDS.get(med_key, '')

    # تحقق إن الحرف واحد من الأوامر المعروفة (A B C D S)
    valid_commands = set(SERIAL_COMMANDS.values())
    if not cmd or cmd not in valid_commands:
        print(f'[Server] ❌ No valid command for medicine: {medicine!r}  (cmd={cmd!r})')
        return jsonify({
            'ok'   : False,
            'error': f'No command mapped for: {medicine}',
            'valid': sorted(valid_commands),
        }), 400

    success = send_command(cmd)
    status  = '✅' if success else '🔕'
    print(f'[Server] {status}  cmd={cmd!r}  ← medicine={medicine!r}  '
          f'(serial={"OK" if success else "OFFLINE"})')

    return jsonify({
        'ok'          : True,
        'command_sent': cmd,
        'medicine'    : medicine,
        'serial_active': success,
    })

# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════
if __name__ == '__main__':
    init_serial()
    print(f'\n[Server] 🚀  Running on http://0.0.0.0:{SERVER_PORT}')
    print(f'[Server]     الـ HTML هيبعت على http://raspberrypi.local:{SERVER_PORT}/send')
    print(f'[Server]     اضغط Ctrl+C للإيقاف\n')
    print('[Server] خريطة الأوامر:')
    for med, ch in SERIAL_COMMANDS.items():
        print(f'           {med:<15} → {ch!r}')
    print()
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False)
