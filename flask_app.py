import sqlite3
import os
import pytz
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, g

app = Flask(__name__)

# CONFIGURACIÓN DE RUTAS (Portable)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'negocio_v2.db')


def get_db():
    """Abre una nueva conexión si no existe una para la petición actual."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # Esto permite acceder a las columnas por nombre: fila['nombre']
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Cierra la conexión automáticamente al terminar la petición web."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def obtener_hora_mty():
    zona_horaria = pytz.timezone('America/Monterrey')
    return datetime.now(zona_horaria)


def init_db():
    """Crea las tablas si no existen al iniciar la app."""
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS productos
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, precio REAL, costo REAL, stock INTEGER, stock_inicial INTEGER)''')
        db.execute('''CREATE TABLE IF NOT EXISTS ventas
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, monto REAL, fecha DATETIME)''')
        db.execute('''CREATE TABLE IF NOT EXISTS gastos
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha DATETIME)''')
        db.execute('''CREATE TABLE IF NOT EXISTS retiros
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha DATETIME)''')
        db.execute('''CREATE TABLE IF NOT EXISTS bitacora_stock
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, cantidad INTEGER, tipo TEXT, fecha DATETIME)''')
        db.commit()


@app.route('/')
def index():
    db = get_db()
    prods = db.execute(
        "SELECT * FROM productos ORDER BY nombre ASC").fetchall()

    ahora = obtener_hora_mty()
    hoy = ahora.strftime("%Y-%m-%d")

    # SQL con marcadores '?' para evitar inyecciones (Seguridad)
    utilidad_hoy = db.execute("""
        SELECT COALESCE(SUM(v.monto - p.costo), 0)
        FROM ventas v JOIN productos p ON v.producto_id = p.id
        WHERE v.fecha LIKE ?""", (f"{hoy}%",)).fetchone()[0]

    gastos_hoy = db.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM gastos WHERE fecha LIKE ?", (f"{hoy}%",)).fetchone()[0]
    retiros_hoy = db.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM retiros WHERE fecha LIKE ?", (f"{hoy}%",)).fetchone()[0]

    return render_template('index.html',
                           productos=prods,
                           corte_hoy=utilidad_hoy,
                           gastos_hoy=gastos_hoy,
                           retiros_hoy=retiros_hoy,
                           ganancia_hoy=(
                               utilidad_hoy - gastos_hoy - retiros_hoy),
                           datetime_now=ahora.strftime("%d/%m/%Y %H:%M"))


@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form.get('nombre')
    precio = float(request.form.get('precio'))
    costo = float(request.form.get('costo'))
    stock = int(request.form.get('stock'))
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    cursor = db.execute("""
        INSERT INTO productos (nombre, precio, costo, stock, stock_inicial) 
        VALUES (?, ?, ?, ?, ?)
    """, (nombre, precio, costo, stock, stock))

    p_id = cursor.lastrowid
    db.execute("INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, ?, 'ALTA INICIAL', ?)",
               (p_id, stock, fecha))
    db.commit()
    return redirect(url_for('index'))


@app.route('/registrar_venta', methods=['POST'])
def registrar_venta():
    p_id = request.form['producto_id']
    fecha = obtener_hora_mty().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    p = db.execute("SELECT * FROM productos WHERE id=?", (p_id,)).fetchone()

    if p and p['stock'] > 0:
        db.execute("UPDATE productos SET stock = stock - 1 WHERE id=?", (p_id,))
        db.execute("INSERT INTO ventas (producto_id, monto, fecha) VALUES (?,?,?)",
                   (p_id, p['precio'], fecha))
        db.execute(
            "INSERT INTO bitacora_stock (producto_id, cantidad, tipo, fecha) VALUES (?, -1, 'VENTA', ?)", (p_id, fecha))
        db.commit()
    return redirect(url_for('index'))


@app.route('/historial')
def historial():
    db = get_db()
    reporte = db.execute("""
        SELECT strftime('%Y-%m', v.fecha) AS mes, 
               SUM(v.monto - p.costo) AS total_mes,
               COALESCE((SELECT SUM(monto) FROM gastos WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', v.fecha)), 0) AS gastos_mes,
               COALESCE((SELECT SUM(monto) FROM retiros WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', v.fecha)), 0) AS retiros_mes
        FROM ventas v 
        JOIN productos p ON v.producto_id = p.id 
        GROUP BY mes 
        ORDER BY mes DESC""").fetchall()

    ventas = db.execute(
        "SELECT v.id, p.nombre, v.monto, v.fecha FROM ventas v JOIN productos p ON v.producto_id = p.id ORDER BY v.fecha DESC LIMIT 50").fetchall()
    return render_template('historial.html', reporte=reporte, ventas=ventas)


init_db()

if __name__ == '__main__':
    app.run(debug=True)
