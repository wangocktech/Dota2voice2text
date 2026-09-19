import sounddevice as sd


def get_input_devices():
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    result = []

    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue

        hostapi_index = int(device["hostapi"])
        hostapi_name = hostapis[hostapi_index]["name"]

        result.append(
            {
                "index": index,
                "name": device["name"],
                "channels": int(device["max_input_channels"]),
                "sample_rate": int(device["default_samplerate"]),
                "hostapi": hostapi_name,
            }
        )

    return result


if __name__ == "__main__":
    devices = get_input_devices()

    print()
    print("Доступные устройства ввода:")
    print()

    for device in devices:
        print(
            f'[{device["index"]}] '
            f'{device["name"]} | '
            f'{device["hostapi"]} | '
            f'{device["channels"]} ch | '
            f'{device["sample_rate"]} Hz'
        )
