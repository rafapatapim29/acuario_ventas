import sqlite3
import os
import pytz
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Configuración de rutas
if os.path.exists('/home/rafahost/'):
    BASE_DIR = '/home/rafahost/acuario_ventas'
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, 'negocio_v2.db')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def obtener_hora_mty():
    zona_horaria = pytz.timezone('America/Monterrey')
    return datetime.now(zona_horaria)


def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS productos
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, precio REAL, costo REAL, stock INTEGER, stock_inicial INTEGER)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ventas
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, monto REAL, fecha DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS gastos
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS retiros
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS bitacora_stock
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, cantidad INTEGER, tipo TEXT, fecha DATETIME)''')
        conn.commit()


@app.route('/')
def index():
    conn = get_db()
    prods = conn.execute(
        "SELECT * FROM productos ORDER BY nombre ASC").fetchall()
    ahora = obtener_hora_mty()
    hoy = ahora.strftime("%Y-%m-%d")

    utilidad_hoy = conn.execute("""
        SELECT COALESCE(SUM(v.monto - p.costo), 0)
        FROM ventas v JOIN productos p ON v.producto_id = p.id
        WHERE v.fecha LIKE ?""", (f"{hoy}%",)).fetchone()[0]

    gastos_hoy = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM gastos WHERE fecha LIKE ?", (f"{hoy}%",)).fetchone()[0]
    retiros_hoy = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM retiros WHERE fecha LIKE ?", (f"{hoy}%",)).fetchone()[0]

    conn.close()
    return render_template('index.html', productos=prods, corte_hoy=utilidad_hoy,
                           gastos_hoy=gastos_hoy, retiros_hoy=retiros_hoy,
                           ganancia_hoy=(
                               utilidad_hoy - gastos_hoy - retiros_hoy),
                           datetime_now=ahora.strftime("%d/%m/%Y %H:%M"))

# NUEVA RUTA: Para dar de alta productos por primera vez


@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form.get('nombre')
    precio = float(request.form.get('precio'))
    costo = float(request.form.get('costo'))
    stock = int(request.form.get('stock'))
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO productos (nombre, precio, costo, stock, stock_inicial) 
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, precio, costo, stock, stock))
        p_id = cursor.lastrowid
        # Registrar en bitácora
        conn.execute("INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, ?, 'ALTA INICIAL', ?)",
                     (p_id, stock, fecha))
    return redirect(url_for('index'))


@app.route('/registrar_venta', methods=['POST'])
def registrar_venta():
    p_id = request.form['producto_id']
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        p = conn.execute("SELECT * FROM productos WHERE id=?",
                         (p_id,)).fetchone()
        if p and p['stock'] > 0:
            conn.execute(
                "UPDATE productos SET stock = stock - 1 WHERE id=?", (p_id,))
            conn.execute(
                "INSERT INTO ventas (producto_id, monto, fecha) VALUES (?,?,?)", (p_id, p['precio'], fecha))
            conn.execute(
                "INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, -1, 'VENTA', ?)", (p_id, fecha))
    return redirect(url_for('index'))


@app.route('/entrada_stock', methods=['POST'])
def entrada_stock():
    p_id = request.form.get('producto_id')
    cantidad = int(request.form.get('cantidad'))
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute(
            "UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, p_id))
        conn.execute(
            "INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, ?, 'ENTRADA MANUAL', ?)", (p_id, cantidad, fecha))
    return redirect(url_for('index'))


@app.route('/registrar_gasto', methods=['POST'])
def registrar_gasto():
    concepto = request.form['concepto']
    monto = float(request.form['monto'])
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO gastos (concepto, monto, fecha) VALUES (?,?,?)", (concepto, monto, fecha))
    return redirect(url_for('index'))


@app.route('/historial')
def historial():
    conn = get_db()
    reporte = conn.execute("""
        SELECT strftime('%Y-%m', v.fecha) AS mes, SUM(v.monto - p.costo) AS total_mes,
        COALESCE((SELECT SUM(monto) FROM gastos WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', v.fecha)), 0) AS gastos_mes,
        COALESCE((SELECT SUM(monto) FROM retiros WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', v.fecha)), 0) AS retiros_mes
        FROM ventas v JOIN productos p ON v.producto_id = p.id GROUP BY mes ORDER BY mes DESC""").fetchall()

    ventas = conn.execute(
        "SELECT v.id, p.nombre, v.monto, v.fecha FROM ventas v JOIN productos p ON v.producto_id = p.id ORDER BY v.fecha DESC LIMIT 50").fetchall()
    gastos = conn.execute(
        "SELECT * FROM gastos ORDER BY fecha DESC LIMIT 50").fetchall()
    retiros = conn.execute(
        "SELECT * FROM retiros ORDER BY fecha DESC LIMIT 50").fetchall()
    movimientos = conn.execute(
        "SELECT b.*, p.nombre FROM bitacora_stock b JOIN productos p ON b.producto_id = p.id ORDER BY b.fecha DESC LIMIT 50").fetchall()
    conn.close()
    return render_template('historial.html', reporte=reporte, ventas=ventas, gastos=gastos, retiros=retiros, movimientos=movimientos)


@app.route('/eliminar_venta/<int:id>', methods=['POST'])
def eliminar_venta(id):
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        venta = conn.execute(
            "SELECT producto_id FROM ventas WHERE id = ?", (id,)).fetchone()
        if venta:
            conn.execute(
                "UPDATE productos SET stock = stock + 1 WHERE id = ?", (venta['producto_id'],))
            conn.execute("INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, 1, 'VENTA CANCELADA', ?)",
                         (venta['producto_id'], fecha))
            conn.execute("DELETE FROM ventas WHERE id = ?", (id,))
    return redirect(url_for('historial'))


@app.route('/limpiar_todo_el_historial', methods=['POST'])
def limpiar_todo_el_historial():
    with get_db() as conn:
        conn.execute("DELETE FROM ventas")
        conn.execute("DELETE FROM gastos")
        conn.execute("DELETE FROM retiros")
        conn.execute("DELETE FROM bitacora_stock")
    return redirect(url_for('historial'))


with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)
