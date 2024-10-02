import re

__all__ = ["Kuid", "TrainzConfig"]


class Kuid(str):
    def __new__(cls, value):
        if value.startswith("<") and value.endswith(">"):
            value = value[1:-1]

        assert re.match(r"^(?:kuid:-?\d+:\d+|kuid2:-?\d+:\d+:\d+|null)$", value, re.IGNORECASE), f"Invalid KUID: {value}"
        return str.__new__(cls, value.lower())

    def __repr__(self):
        return f"<{self}>"


class TrainzConfig:
    def __init__(self, filename, encoding="utf-8-sig"):
        self.config_data = {}

        path = []
        previous_key = None

        if encoding == "auto":
            try:
                import chardet
                encoding = chardet.detect(open(filename, "rb").read())["encoding"]
            except ModuleNotFoundError as e:
                raise e

        with open(filename, "r", encoding=encoding) as f:
            for line in f.readlines():
                line = line.strip()

                if not line or line.startswith(";"):
                    continue

                split_line = line.split(maxsplit=1)

                if len(split_line) == 1:
                    if split_line[0] == "{":
                        path.append(previous_key)
                    if split_line[0] == "}":
                        path.pop()
                    else:
                        previous_key = split_line[0]
                    continue

                key = split_line[0]
                value = split_line[1]

                if re.match(r'^".*"$', value):
                    value = value[1:-1]
                elif re.match(r'^<.*>$', value):
                    value = Kuid(value)
                elif re.match(r"^[-+]?([0-9]*[.])[0-9]+$", value):
                    value = float(value)
                elif re.match(r"^[-+]?\d+$", value):
                    value = int(value)
                elif "," in value:
                    value = value.split(",")

                container = self.config_data

                for p in path:
                    if p not in container:
                        container[p] = {}

                    container = container[p]

                container[key] = value

    def get(self, path, default=None):
        path = path.split(".")
        container = self.config_data

        for p in path:
            if p not in container:
                return default

            container = container[p]

        return container

    @property
    def kuid(self) -> str:
        return self.config_data.get("kuid")

    @property
    def username(self) -> str:
        return self.config_data.get("username", self.config_data.get("name", self.config_data.get("asset-filename"))).replace("_", " ")

    def __len__(self):
        return len(self.config_data)

    def __getitem__(self, item):
        return self.config_data[item]

    def __setitem__(self, key, value):
        self.config_data[key] = value

    def __iter__(self):
        return iter(self.config_data)

    def __contains__(self, item):
        return item in self.config_data
