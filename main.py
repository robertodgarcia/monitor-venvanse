import sys
import os
import time
import datetime
import csv
import re
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
URL_PRODUTO = "https://www.drogasil.com.br/dimesilato-de-lisdexanfetamina-50mg-pharlab-genericos-30-capsulas-a3-1020864.html?origin=search"
PRECO_MINIMO_ACEITAVEL = 100.00 

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ARQUIVO_RELATORIO = "relatorio_medicamento.csv"
# ---------------------

def limpar_para_numero(texto):
    apenas_numeros = re.sub(r'[^\d,]', '', str(texto))
    if not apenas_numeros: return 0.0
    return float(apenas_numeros.replace(',', '.'))

def formatar_br(valor):
    return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')

# --- NOVA FUNÇÃO: Converte horário do Servidor (UTC) para Brasil (UTC-3) ---
def obter_data_brasil():
    fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_horario)
    return data_hora
# ---------------------------------------------------------------------------

def enviar_telegram(p_orig, p_promo, p_calc):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> Sem credenciais do Telegram. Pulando envio.")
        return

    print("\nEnviando mensagem para o Telegram...")
    
    # Usa a função nova para pegar a hora certa
    agora = obter_data_brasil()
    
    mensagem = (
        f"💊 *Relatório Diário*\n"
        f"📅 {agora.strftime('%d/%m %H:%M')} (Brasília)\n\n"
        f"💰 *Atual:* R$ {p_promo}\n"
        f"📉 *Original:* R$ {p_orig}\n"
        f"------------------\n"
        f"👮 *45% OFF:* R$ {p_calc}\n"
        f"------------------\n"
        f"🔗 [Link Drogasil]({URL_PRODUTO})"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    
    try:
        requests.post(url, json=payload)
        print(">> Telegram enviado!")
    except Exception as e:
        print(f">> Erro Telegram: {e}")

def capturar_preco():
    print("--- Iniciando Modo Furtivo (Stealth) ---")
    driver = None

    try:
        options = webdriver.ChromeOptions()
        
        # Configuração Anti-Bloqueio
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Configuração de Nuvem
        options.add_argument("--headless=new") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Script extra
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"Acessando: {URL_PRODUTO}")
        driver.get(URL_PRODUTO)
        time.sleep(15) 
        
        print(f"Pagina: {driver.title}")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. JSON
        preco_promocional_final = 0.0
        scripts_json = soup.find_all('script', {'type': 'application/ld+json'})
        for script in scripts_json:
            try:
                if not script.string: continue
                dados = json.loads(script.string)
                if isinstance(dados, dict) and dados.get('@type') == 'Product':
                    offers = dados.get('offers')
                    if isinstance(offers, list):
                        preco_promocional_final = float(offers[0].get('price', 0))
                    elif isinstance(offers, dict):
                        preco_promocional_final = float(offers.get('price', 0))
                    if preco_promocional_final > 0: break
            except: continue

        # 2. VISUAL
        elementos_visuais = soup.find_all(string=lambda text: text and "R$" in text)
        lista_valores = []
        for texto in elementos_visuais:
            val = limpar_para_numero(texto.strip())
            if val > PRECO_MINIMO_ACEITAVEL:
                lista_valores.append(val)
        
        lista_valores = sorted(list(set(lista_valores)))

        # 3. LÓGICA
        if preco_promocional_final == 0.0:
            preco_promocional_final = lista_valores[0] if lista_valores else 0.0

        candidatos_original = [x for x in lista_valores if x > (preco_promocional_final + 1.00)]
        if candidatos_original:
            preco_original_final = min(candidatos_original)
        else:
            preco_original_final = preco_promocional_final

        valor_com_45_off = preco_original_final * 0.55
        
        p_orig_str = formatar_br(preco_original_final)
        p_promo_str = formatar_br(preco_promocional_final)
        p_calc_str = formatar_br(valor_com_45_off)

        print(f"RESULTADO: Original={p_orig_str} | Promo={p_promo_str}")
        
        if preco_promocional_final > 0:
            gravar_no_csv(p_orig_str, p_promo_str, p_calc_str)
            enviar_telegram(p_orig_str, p_promo_str, p_calc_str)
        else:
            print("ERRO: Bloqueio ou pagina vazia.")

    except Exception as e:
        print(f"ERRO FATAL: {e}")
    
    finally:
        if driver: driver.quit()

def gravar_no_csv(p_original, p_promocional, p_calculado):
    arquivo_existe = os.path.isfile(ARQUIVO_RELATORIO)
    with open(ARQUIVO_RELATORIO, mode='a', newline='', encoding='utf-8-sig') as arquivo:
        writer = csv.writer(arquivo, delimiter=';')
        if not arquivo_existe:
            writer.writerow(["Data", "Hora", "Original", "Atual", "45% OFF"])
        
        # Usa a função nova aqui também para salvar correto no CSV
        agora = obter_data_brasil()
        data_str = agora.strftime("%d/%m/%Y")
        hora_str = agora.strftime("%H:%M:%S")
        
        writer.writerow([data_str, hora_str, p_original, p_promocional, p_calculado])
        print("CSV atualizado com horario BR.")

if __name__ == "__main__":
    capturar_preco()
