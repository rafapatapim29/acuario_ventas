Markdown
# Sistema de Gestión para Acuario

Este es un sistema web desarrollado con **Python** y **Flask** para controlar el inventario, ventas y flujo de caja de un acuario.


## Características
- **Inventario**: Control de stock en tiempo real.
- **Ventas**: Registro rápido de salidas con descuento automático de stock.
- **Finanzas**: Cálculo de utilidad bruta, gastos y ganancia neta diaria.
- **Historial**: Bitácora de movimientos de stock y reportes mensuales.


## Instalación local
1. Clona el repositorio.
2. Crea un entorno virtual: `python -m venv venv`.
3. Activa el entorno e instala las dependencias:
   ```bash
   pip install flask pytz
Ejecuta la aplicación:

Bash
python flask_app.py
📝 Notas
La base de datos se genera automáticamente al iniciar la aplicación por primera vez.
