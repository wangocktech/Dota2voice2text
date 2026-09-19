import sounddevice as sd


def get_input_devices():
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    # На Windows нам нужны именно Core Audio endpoints через WASAPI.
    wasapi_index = None

    for index, api in enumerate(hostapis):
        if "WASAPI" in api["name"].upper():
            wasapi_index = index
            break

    result = []

    # Если WASAPI почему-то отсутствует, используем обычный список
    # как fallback.
    if wasapi_index is None:
        for index, device in enumerate(devices):
            if device["max_input_channels"] <= 0:
                continue

            hostapi_index = int(device["hostapi"])

            result.append(
                {
                    "index": index,
                    "name": device["name"],
                    "channels": int(device["max_input_channels"]),
                    "sample_rate": int(device["default_samplerate"]),
                    "hostapi": hostapis[hostapi_index]["name"],
                    "default": False,
                }
            )

        return result

    default_input = int(
        hostapis[wasapi_index].get(
            "default_input_device",
            -1,
        )
    )

    seen = set()

    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue

        if int(device["hostapi"]) != wasapi_index:
            continue

        name = device["name"].strip()

        # На всякий случай не показываем один endpoint дважды.
        key = name.casefold()

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                "index": index,
                "name": name,
                "channels": int(device["max_input_channels"]),
                "sample_rate": int(device["default_samplerate"]),
                "hostapi": "Windows WASAPI",
                "default": index == default_input,
            }
        )

    # Микрофон Windows по умолчанию идёт первым.
    result.sort(
        key=lambda device: (
            not device["default"],
            device["name"].casefold(),
        )
    )

    return result


if __name__ == "__main__":
    print()
    print("Устройства ввода Windows:")
    print()

    for device in get_input_devices():
        default = (
            " [ПО УМОЛЧАНИЮ]"
            if device["default"]
            else ""
        )

        print(
            f'[{device["index"]}] '
            f'{device["name"]}{default} | '
            f'{device["sample_rate"]} Hz'
        )
