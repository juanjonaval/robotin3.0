import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json
import logging
import sys

# Configuración de logging
log_file = os.path.join("C:\\robapp\\binary", "robotin.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.info("Logging inicializado correctamente.")

# Carga de configuración
config_path = r"C:\robapp\robotin3.0"
config_file = os.path.join(config_path, "config.json")
try:
    with open(config_file, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    logging.error(f"Error: config.json no encontrado en {config_path}")
    sys.exit(1)
except json.JSONDecodeError:
    logging.error("Error: formato JSON inválido en config.json")
    sys.exit(1)

# Parámetros de mercado
symbol      = config["symbol"]
timeframe   = getattr(mt5, config["timeframe"].split(".")[-1])
lookback    = config["lookback"]
ema_length  = config["ema_length"]
leftBars    = config["leftBars"]
rightBars   = config["rightBars"]
tolerance   = config["tolerance"]

# Parámetros de trading
lot_size    = config.get("lot_size", 0.1)
tp_pips     = config.get("tp_pips", 200)
sl_pips     = config.get("sl_pips", 200)
deviation   = config.get("deviation", 10)
magic       = config.get("magic", 123456)

# Inicializar MetaTrader 5
def init_mt5():
    if not mt5.initialize():
        logging.error("❌ Error al conectar con MetaTrader 5")
        sys.exit(1)
    if not mt5.symbol_select(symbol, True):
        logging.error(f"❌ No se pudo seleccionar el símbolo {symbol}")
        mt5.shutdown()
        sys.exit(1)

# Funciones auxiliares
def calcular_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def is_unique(val, niveles):
    return all(abs(n - val) >= tolerance for n in niveles)

def detectar_pivot(df, i, lado='high'):
    if i < leftBars or i > len(df) - rightBars - 1:
        return False
    val = df.iloc[i][lado]
    # Check left side
    for j in range(1, leftBars + 1):
        if (df.iloc[i - j][lado] >= val if lado == 'high' else df.iloc[i - j][lado] <= val):
            return False
    # Check right side
    for j in range(1, rightBars + 1):
        if (df.iloc[i + j][lado] >= val if lado == 'high' else df.iloc[i + j][lado] <= val):
            return False
    return True

# Log con hora local Buenos Aires
def loggear_local(tipo, valor, tiempo):
    tiempo_str = tiempo.strftime('%Y-%m-%d %H:%M:%S')
    mensaje = f"{tiempo_str} - {tipo}: {valor:.2f}"
    print(mensaje)
    with open(log_file, 'a') as f:
        f.write(mensaje + '\n')

# Función para abrir orden
def abrir_orden(tipo_orden, precio, sl, tp):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": tipo_orden,
        "price": precio,
        "sl": sl,
        "tp": tp,
        "deviation": deviation,
        "magic": magic,
        "comment": "Bot Soportes_Resistencias",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Error abriendo orden: {result.comment}")
    else:
        logging.info(f"Orden abierta exitosamente: ticket={result.order}")

# Inicio del bot
def main():
    init_mt5()
    resistencias = []
    soportes = []
    logging.info("✅ Bot iniciado. Monitoreando niveles en tiempo real...")

    while True:
        # Obtener datos
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback + rightBars + 10)
        if rates is None or len(rates) == 0:
            logging.warning("No se pudieron obtener datos. Reintentando en 10 segundos.")
            time.sleep(10)
            continue

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=6)
        df['ema'] = calcular_ema(df['close'], ema_length)

        # Revisar cada barra para pivotes
        for i in range(len(df) - rightBars):
            tiempo = df.iloc[i]['time']
            # Pivote alto -> resistencia
            if detectar_pivot(df, i, 'high'):
                nivel = df.iloc[i]['high']
                if is_unique(nivel, resistencias):
                    resistencias.append(nivel)
                    loggear_local("Resistencia", nivel, tiempo)

                    # Operar venta si no hay posiciones abiertas
                    if not mt5.positions_get(symbol=symbol):
                        tick = mt5.symbol_info_tick(symbol)
                        price = tick.bid
                        point = mt5.symbol_info(symbol).point
                        sl_price = price + sl_pips * point
                        tp_price = price - tp_pips * point
                        abrir_orden(mt5.ORDER_TYPE_SELL, price, sl_price, tp_price)

            # Pivote bajo -> soporte
            if detectar_pivot(df, i, 'low'):
                nivel = df.iloc[i]['low']
                if is_unique(nivel, soportes):
                    soportes.append(nivel)
                    loggear_local("Soporte", nivel, tiempo)

                    # Operar compra si no hay posiciones abiertas
                    if not mt5.positions_get(symbol=symbol):
                        tick = mt5.symbol_info_tick(symbol)
                        price = tick.ask
                        point = mt5.symbol_info(symbol).point
                        sl_price = price - sl_pips * point
                        tp_price = price + tp_pips * point
                        abrir_orden(mt5.ORDER_TYPE_BUY, price, sl_price, tp_price)

        time.sleep(60)

if __name__ == "__main__":
    main()
