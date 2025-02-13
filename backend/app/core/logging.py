import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(name: str) -> logging.Logger:
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 포맷터 생성
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 파일 핸들러 생성 (logs 디렉토리에 로그 파일 저장)
    file_handler = RotatingFileHandler(
        f'logs/{name}.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger