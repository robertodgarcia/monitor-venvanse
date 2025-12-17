import sys
import os
import time
import datetime
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By # Necessário para encontrar o preço
from webdriver_manager.chrome import ChromeDriverManager
# Importações para edição de imagem
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURAÇÕES ---
URL_PRODUTO = "https://www.drogasil.com.br/dimesilato-de-lisdexanfetamina-50mg-pharlab-genericos-30-capsulas-a3-1020864.html?origin=search"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# Seletor CSS para o preço na Drogasil (pode mudar se o site atualizar)
SELECTOR_PRECO = ".product-price__main"
# ---------------------

def obter_data_brasil():
    fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_horario)
    return data_hora

def editar_imagem_com_timestamp(caminho_arquivo):
    """Edita a imagem salva para inserir o carimbo de data/hora."""
    try:
        print(">> Iniciando edição da imagem...")
        agora = obter_data_brasil()
        texto = agora.strftime('%d/%m/%Y\n%H:%M (BRT)')

        img = Image.open(caminho_arquivo)
        draw = ImageDraw.Draw(img)

        # Tenta carregar uma fonte TTF padrão do Linux para ficar mais bonito e maior.
        # Se falhar, usa a fonte padrão do Pillow (que é pequena).
        try:
            # Caminho comum em ambientes Linux/Docker usado no GH Actions
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except IOError:
            print(">> Aviso: Fonte TTF não encontrada, usando fonte padrão (pequena).")
            font = ImageFont.load_default()

        # Cálculos para centralizar o texto verticalmente à direita
        img_w, img_h = img.size
        
        # Usa textbbox (método mais recente do Pillow) para obter dimensões do texto
        bbox = draw.textbbox((0, 0), texto, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Posição X: Largura total menos largura do texto menos uma margem de 50px
        pos_x = img_w - text_w - 50
        # Posição Y: Metade da altura total menos metade da altura do texto
        pos_y = (img_h - text_h) / 2

        # Desenha o texto em vermelho (RGB: 255, 0, 0)
        draw.text((pos_x, pos_y), texto, font=font, fill=(255, 0, 0), align="center")

        # Salva a imagem editada por cima da original
        img.save(caminho_arquivo)
        print(">> Imagem editada com sucesso.")
        return True
    except Exception as e:
        print(f">> Erro ao editar imagem: {e}")
        return False

def gerar_caption_baseado_no_preco(preco_texto_bruto):
    """Gera a legenda do Telegram baseada nas regras de negócio."""
    if not preco_texto_bruto:
        return "⚠️ Não foi possível identificar o preço na página."

    try:
        # Limpa o texto (ex: "R$ 346,62") para virar número (346.62)
        # Remove R$, remove pontos de milhar, troca vírgula decimal por ponto
        preco_limpo = preco_texto_bruto.replace("R$", "").replace(".", "").replace(",", ".").strip()
        preco_float = float(preco_limpo)

        # Lógica de comparação solicitada
        # Usando >= para cobrir o valor exato e superiores
        if preco_float >= 346.62:
            status = "o valor está dentro do normal"
        # Cobre 326.00 até 346.61
        elif preco_float >= 326.00:
            status = "o valor está baixo"
        # Menor que 326.00
        else:
            status = "🚨 ALERTA: o valor está mais baixo ainda"

        caption = f"💰 Valor no print: {preco_texto_bruto}\nStatus: {status}"
        return caption

    except ValueError:
        return f"⚠️ Erro ao converter preço: {preco_texto_bruto}"


def enviar_screenshot_telegram(caminho_arquivo, caption_personalizado):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> Sem credenciais do Telegram. Pulando envio.")
        return

    print("\nEnviando screenshot para o Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    # Adiciona o link no final do caption
    full_caption = f"{caption_personalizado}\n\n🔗 [Link Drogasil]({URL_PRODUTO})"
    
    files = {'photo': open(caminho_arquivo, 'rb')}
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": full_caption, "parse_mode": "Markdown"}
    
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
    print("--- Iniciando Captura e Processamento ---")
    driver = None
    preco_texto = None

    try:
        options = webdriver.ChromeOptions()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--headless=new") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Aumentei um pouco a altura para garantir que pegue tudo
        options.add_argument("--window-size=1920,1200")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"Acessando: {URL_PRODUTO}")
        driver.get(URL_PRODUTO)
        
        # Espera para garantir o carregamento do preço
        time.sleep(15) 

        # TENTATIVA DE EXTRAIR O PREÇO (TEXTO)
        try:
            element_preco = driver.find_element(By.CSS_SELECTOR, SELECTOR_PRECO)
            preco_texto = element_preco.text.strip()
            print(f"Preço encontrado na página: {preco_texto}")
        except Exception as e:
            print(f"Não foi possível extrair o texto do preço: {e}")
            preco_texto = None # Garante que é None se falhar

        
        # CAPTURA DE TELA
        driver.save_screenshot(NOME_ARQUIVO_SS)
        print(f"Screenshot inicial salvo como {NOME_ARQUIVO_SS}")

    except Exception as e:
        print(f"ERRO FATAL DURANTE A NAVEGAÇÃO: {e}")
        if driver: driver.quit()
        return # Sai se der erro na captura
    
    finally:
        if driver: driver.quit()

    # --- FASE DE PROCESSAMENTO DE IMAGEM ---
    # Se o arquivo foi gerado, vamos editá-lo
    if os.path.exists(NOME_ARQUIVO_SS):
        # Edita a imagem inserindo o horário
        editar_imagem_com_timestamp(NOME_ARQUIVO_SS)
        
        # Gera o caption baseado no preço que tentamos extrair
        caption_final = gerar_caption_baseado_no_preco(preco_texto)

        # ENVIO PARA O TELEGRAM
        enviar_screenshot_telegram(NOME_ARQUIVO_SS, caption_final)
    else:
        print("Erro: Arquivo de screenshot não foi gerado.")


if __name__ == "__main__":
    capturar_e_processar()
