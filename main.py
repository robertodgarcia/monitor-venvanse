import sys
import os
import time
import datetime
# import csv # Não é mais necessário para este objetivo
# import re # Não é mais necessário para este objetivo
# import json # Não é mais necessário para este objetivo
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
# from bs4 import BeautifulSoup # Não é mais necessário para este objetivo

# --- CONFIGURAÇÕES ---
URL_PRODUTO = "https://www.drogasil.com.br/dimesilato-de-lisdexanfetamina-50mg-pharlab-genericos-30-capsulas-a3-1020864.html?origin=search"
# PRECO_MINIMO_ACEITAVEL = 100.00 # Não é mais necessário

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ARQUIVO_RELATORIO = "relatorio_medicamento.csv" # Não é mais necessário
# ---------------------

def obter_data_brasil():
    fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_horario)
    return data_hora

def enviar_screenshot_telegram(caminho_arquivo):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> Sem credenciais do Telegram. Pulando envio.")
        return

    print("\nEnviando screenshot para o Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    agora = obter_data_brasil()
    caption = (
        f"💊 *Preço capturado*\n"
        f"📅 {agora.strftime('%d/%m %H:%M')} (Brasília)\n"
        f"🔗 [Link Drogasil]({URL_PRODUTO})"
    )
    
    files = {'photo': open(caminho_arquivo, 'rb')}
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
    
    try:
        requests.post(url, data=payload, files=files)
        print(">> Screenshot enviado com sucesso!")
    except Exception as e:
        print(f">> Erro Telegram (Envio de Imagem): {e}")

    # Limpa o arquivo local após o envio
    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)

def capturar_preco():
    NOME_ARQUIVO_SS = "preco_medicamento.png"
    print("--- Iniciando Captura de Tela ---")
    driver = None

    try:
        options = webdriver.ChromeOptions()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--headless=new") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"Acessando: {URL_PRODUTO}")
        driver.get(URL_PRODUTO)
        
        # Espera para garantir o carregamento do preço
        time.sleep(15) 
        
        # CAPTURA DE TELA
        driver.save_screenshot(NOME_ARQUIVO_SS)
        print(f"Screenshot salvo como {NOME_ARQUIVO_SS}")
        
        # ENVIO
        enviar_screenshot_telegram(NOME_ARQUIVO_SS)

    except Exception as e:
        print(f"ERRO FATAL DURANTE A CAPTURA: {e}")
    
    finally:
        if driver: driver.quit()

# As funções 'limpar_para_numero', 'formatar_br', 'enviar_telegram' (antiga) e 'gravar_no_csv' foram removidas
# por não serem mais necessárias para a captura de tela.

if __name__ == "__main__":
    capturar_preco()
