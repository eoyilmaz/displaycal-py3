import configparser


class CaseSensitiveConfigParser(configparser.RawConfigParser):
    def optionxform(self, optionstr):
        return optionstr
