import asyncio
import psutil
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from config import TOKEN, CHAT_ID
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


bot = Bot(token=TOKEN)
dp = Dispatcher()

CPU_THRESHOLD = 80
RAM_THRESHOLD = 85
DISK_THRESHOLD = 90
TEMP_THRESHOLD = 80

last_alerts = {"cpu": False, "ram": False, "disk": False, "temp": False}

@dp.message(Command('start'))
async def user(message: types.Message):
    logging.info('Прожата команда!')
    await user_mon()


async def get_cpu_temp():
    """Получает температуру процессора из сенсора it8728 temp3 (Intel PECI)"""
    try:
        temps = psutil.sensors_temperatures()

        coretemp_key = next((k for k in temps if k.startswith("coretemp")), None)

        if coretemp_key:

            for sensor in temps[coretemp_key]:
                if "Package" in sensor.label or "Pkg" in sensor.label:
                    logging.info(f"🔥 Температура CPU (Package): {sensor.current}°C")
                    return sensor.current

            core_temps = [s.current for s in temps[coretemp_key] if "Core" in s.label]
            if core_temps:
                max_temp = max(core_temps)
                logging.info(f"🔥 Температура CPU (макс. ядро): {max_temp}°C")
                return max_temp
    except Exception as e:
        logging.error(f"Ошибка при получении температуры: {e}")
        return "N/A"


async def get_gpu_temp():
    """Получает температуру GPU из сенсора nouveau (temp1)"""
    try:
        temps = psutil.sensors_temperatures()

        nouveau_key = next((k for k in temps if "nouveau" in k), None)

        if nouveau_key:
            # Ищем основной сенсор температуры (обычно temp1)
            for sensor in temps[nouveau_key]:
                if sensor.label == "temp1" or "GPU" in sensor.label:
                    logging.info(f"🎮 Температура GPU ({nouveau_key}): {sensor.current}°C")
                    return sensor.current

            if temps[nouveau_key]:
                logging.info(f"🎮 Температура GPU ({nouveau_key}, первый сенсор): {temps[nouveau_key][0].current}°C")
                return temps[nouveau_key][0].current

        logging.warning("⚠️ Не удалось определить сенсор температуры GPU!")
        return "N/A"

    except Exception as e:
        logging.error(f"Ошибка при получении температуры GPU: {e}")
        return "N/A"


async def monitor_server(GPU_TEMP_THRESHOLD=50):
    """Постоянный мониторинг системы (каждую минуту)"""
    global last_alerts
    while True:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        cpu_temp = await get_cpu_temp()
        gpu_temp = await get_gpu_temp()

        logging.info(f"📊 CPU: {cpu}%, RAM: {memory}%, Disk: {disk}%, Temp CPU: {cpu_temp}°C")


        await send_alert("cpu", cpu, CPU_THRESHOLD, "⚠️ Высокая загрузка CPU!")
        await send_alert("ram", memory, RAM_THRESHOLD, "⚠️ Высокая загрузка RAM!")
        await send_alert("disk", disk, DISK_THRESHOLD, "⚠️ Диск почти заполнен!")
        if cpu_temp != "N/A" and isinstance(cpu_temp, (int, float)) and cpu_temp > TEMP_THRESHOLD:
            await send_alert("temp", cpu_temp, TEMP_THRESHOLD, "🔥 Высокая температура CPU!")
        if gpu_temp != "N/A" and isinstance(gpu_temp, (int, float)) and gpu_temp > GPU_TEMP_THRESHOLD:
            await send_alert("gpu_temp", gpu_temp, GPU_TEMP_THRESHOLD, "🔥 Высокая температура GPU!")

        await asyncio.sleep(60)  # Проверяем раз в минуту

async def user_mon():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    cpu_temp = await get_cpu_temp()
    gpu_temp = await get_gpu_temp()

    message = (
        f"📊 *Мониторинг сервера*\n"
        f"💻 CPU: {cpu}%\n"
        f"📈 RAM: {memory}%\n"
        f"💾 Disk: {disk}%\n"
        f"🔥 Температура CPU: {cpu_temp}°C\n"
        f'🔥 Температура GPU: {gpu_temp}°C'
    )

    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        logging.info("✅ Ежечасный мониторинг отправлен в Telegram")
    except Exception as e:
        logging.error(f"Ошибка отправки мониторинга: {e}")
async def send_monitoring():
    """Отправка общего отчёта раз в час"""
    while True:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        cpu_temp = await get_cpu_temp()
        gpu_temp = await get_gpu_temp()

        message = (
            f"📊 *Мониторинг сервера*\n"
            f"💻 CPU: {cpu}%\n"
            f"📈 RAM: {memory}%\n"
            f"💾 Disk: {disk}%\n"
            f"🔥 Температура CPU: {cpu_temp}°C\n"
            f'🔥 Температура GPU: {gpu_temp}°C'
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            logging.info("✅ Ежечасный мониторинг отправлен в Telegram")
        except Exception as e:
            logging.error(f"Ошибка отправки мониторинга: {e}")

        await asyncio.sleep(3600)  # Отправляем раз в час


async def send_alert(param, value, threshold, alert_message):
    """Отправляет предупреждение сразу при превышении порога"""
    if value > threshold and not last_alerts[param]:
        try:
            await bot.send_message(chat_id=CHAT_ID, text=f"{alert_message}\nТекущее значение: {value}%", parse_mode="Markdown")
            logging.warning(f"⚠️ Отправлено предупреждение: {alert_message} ({value}%)")
        except Exception as e:
            logging.error(f"Ошибка отправки предупреждения: {e}")
        last_alerts[param] = True
    elif value <= threshold and last_alerts[param]:
        last_alerts[param] = False
        logging.info(f"✅ Проблема с {param} устранена.")


async def main():
    logging.info("🚀 Запуск мониторинга сервера...")
    asyncio.create_task(monitor_server())  # Запускаем постоянный мониторинг
    asyncio.create_task(send_monitoring())  # Запускаем ежечасный репорт
    await dp.start_polling(bot)  # Запускаем обработку входящих обновлений


if __name__ == "__main__":
    asyncio.run(main())
