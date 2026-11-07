import sys
import os

class DualLogger:
    """Redireciona a saída padrão para o terminal e simultaneamente para um arquivo de log"""
    def __init__(self, filename="execucao.log", mode="w", encoding="utf-8"):
        self.terminal = sys.stdout

        pasta = os.path.dirname(filename)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

        self.log = open(filename, mode, encoding=encoding)

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        if hasattr(self, 'log') and not self.log.closed:
            self.log.close()

def ativar_logger(nome_arquivo="execucao.log", mode="w"):
    """Função auxiliar para ativar o DualLogger de forma simples"""
    logger = DualLogger(filename=nome_arquivo, mode=mode)
    sys.stdout = logger
    return logger