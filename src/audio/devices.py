import sounddevice as sd


def get_input_devices():
    devices = sd.query_devices()
    input_devices = []

    for index, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            input_devices.append(
                {
                    "index": index,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": int(device["default_samplerate"]),
                }
            )

    return input_devices


if __name__ == "__main__":
    devices = get_input_devices()

    print("\nДоступные устройства ввода:\n")

    if not devices:
        print("Микрофоны не найдены.")
        raise SystemExit(1)

    for device in devices:
        print(
            f'[{device["index"]}] {device["name"]} '
            f'| каналов: {device["channels"]} '
            f'| {device["sample_rate"]} Hz'
        )
