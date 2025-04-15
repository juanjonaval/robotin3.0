import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time


# Define the absolute path where config.json is stored
config_path = r"C:\robapp\robotin3.0"  # Change this path if needed
config_file = os.path.join(config_path, "config.json")}
#Read variables
timeframe = config["timeframe"]
lookback = config["lookback"]
ema_length = config["ema_length"]
leftBars = config["leftBars"]
rightBars = config["rightBars"]
tolerance = config["tolerance"] # Ajustá según el tick mínimo del broker
symbol = config["symbol"]
log_file = (config["log_file"])

# Inicializar MetaTrader 5
if not mt5.initialize():
    print("❌ Error al conectar con MetaTrader 5")
    quit()

if not mt5.symbol_select(symbol, True):
    print(f"❌ No se pudo seleccionar el símbolo {symbol}")
    mt5.shutdown()
    quit()

# Funciones auxiliares
def calcular_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def is_unique(val, niveles):
    return all(abs(n - val) >= tolerance for n in niveles)

def detectar_pivot(df, i, lado='high'):
    if i < leftBars or i > len(df) - rightBars - 1:
        return False
    val = df.iloc[i][lado]
    for j in range(1, leftBars + 1):
        if (df.iloc[i - j][lado] >= val if lado == 'high' else df.iloc[i - j][lado] <= val):
            return False
    for j in range(1, rightBars + 1):
        if (df.iloc[i + j][lado] >= val if lado == 'high' else df.iloc[i + j][lado] <= val):
            return False
    return True

# Función para loguear el evento con hora local de Buenos Aires
def loggear_local(tipo, valor, tiempo):
    tiempo_str = tiempo.strftime('%Y-%m-%d %H:%M:%S')
    mensaje = f"{tiempo_str} - {tipo}: {valor:.2f}"
    print(mensaje)
    with open(log_file, 'a') as f:
        f.write(mensaje + '\n')

# Listas de niveles únicos
resistencias = []
soportes = []

print("✅ Bot iniciado. Monitoreando niveles en tiempo real...\n")

# Loop infinito
while True:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback + rightBars + 10)
    if rates is None or len(rates) == 0:
        print("⚠️ No se pudieron obtener datos. Reintentando en 10 segundos.")
        time.sleep(10)
        continue

    df = pd.DataFrame(rates)
    
    # Ajustar manualmente la hora a Buenos Aires (UTC-3)
    df['time'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=6)
    
    df['ema'] = calcular_ema(df['close'], ema_length)

    for i in range(len(df) - rightBars):
        if detectar_pivot(df, i, 'high'):
            nivel = df.iloc[i]['high']
            if is_unique(nivel, resistencias):
                resistencias.append(nivel)
                loggear_local("Resistencia", nivel, df.iloc[i]['time'])

        if detectar_pivot(df, i, 'low'):
            nivel = df.iloc[i]['low']
            if is_unique(nivel, soportes):
                soportes.append(nivel)
                loggear_local("Soporte", nivel, df.iloc[i]['time'])

    time.sleep(60)
