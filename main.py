import sys
import os
import time
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURAÇÕES ---
URL_PRODUTO = "https://www.drogasil.com.br/dimesilato-de-lisdexanfetamina-50mg-pharlab-genericos-30-capsulas-a3-1020864.html?origin=search"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ---------------------

def obter_data_brasil():
    fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_horario)
    return data_hora

def editar_imagem_com_timestamp(caminho_arquivo):
    """Edita a imagem salva para inserir o carimbo de data/hora no canto superior direito."""
    try:
        print(">> Iniciando edição da imagem...")
        agora = obter_data_brasil()
        texto = agora.strftime('%d/%m/%Y\n%H:%M (BRT)')

        img = Image.open(caminho_arquivo)
        draw = ImageDraw.Draw(img)

        try:
            # Tenta carregar fonte padrão do Linux/Docker
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except IOError:
            # Fonte de fallback
            font = ImageFont.load_default()

        img_w, img_h = img.size
        
        # Calcula tamanho do texto
        bbox = draw.textbbox((0, 0), texto, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # --- Nova Posição: Canto Superior Direito ---
        margem = 50
        pos_x = img_w - text_w - margem
        pos_y = margem # Fica no topo com uma margem

        # Escreve em Vermelho (RGB: 255, 0, 0)
        # Adicionei um alinhamento à direita para o texto ficar certinho
        draw.multiline_text((pos_x, pos_y), texto, font=font, fill=(255, 0, 0), align="right")

        img.save(caminho_arquivo)
        print(">> Imagem editada com sucesso (Canto superior direito).")
        return True
    except Exception as e:
        print(f">> Erro ao editar imagem: {e}")
        return False

def enviar_screenshot_telegram(caminho_arquivo):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> Sem credenciais do Telegram. Pulando envio.")
        return

    print("\nEnviando screenshot para o Telegram (Sem caption)...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    # Payload APENAS com o chat_id, sem caption
    files = {'photo': open(caminho_arquivo, 'rb')}
    payload = {"chat_id": TELEGRAM_CHAT_ID}
    
    try:
        requests.post(url, data=payload, files=files)
        print(">> Screenshot enviado com sucesso!")
    except Exception as e:
        print(f">> Erro Telegram (Envio de Imagem): {e}")

    # Limpa o arquivo local após o envio
    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)

def capturar_e_processar():
    NOME_ARQUIVO_SS = "preco_medicamento.png"
    print("--- Iniciando Captura Visual ---")
    driver = None

    try:
        options = webdriver.ChromeOptions()
        # User-agent padrão de desktop
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--headless=new") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # VOLTANDO PARA RESOLUÇÃO FULL HD (Print grande)
        options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print(f"Acessando: {URL_PRODUTO}")
        driver.get(URL_PRODUTO)
        
        # Espera fixa para garantir que o site carregue visualmente
        time.sleep(15) 
        
        # CAPTURA DE TELA APENAS
        driver.save_screenshot(NOME_ARQUIVO_SS)
        print(f"Screenshot salvo como {NOME_ARQUIVO_SS}")

    except Exception as e:
        print(f"ERRO FATAL DURANTE A NAVEGAÇÃO: {e}")
        if driver: driver.quit()
        return
    
    finally:
        if driver: driver.quit()

    # --- PROCESSAMENTO E ENVIO ---
    if os.path.exists(NOME_ARQUIVO_SS):
        # 1. Edita a imagem (coloca data/hora em vermelho no canto superior)
        editar_imagem_com_timestamp(NOME_ARQUIVO_SS)
        
        # 2. Envia para o Telegram sem texto
        enviar_screenshot_telegram(NOME_ARQUIVO_SS)
    else:
        print("Erro: Arquivo de screenshot não foi gerado.")

if __name__ == "__main__":
    capturar_e_processar()
