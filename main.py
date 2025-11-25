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

# --- FUNÇÕES AUXILIARES (Mantidas) ---

def limpar_para_numero(texto):
    # Remove tudo exceto dígitos e vírgula/ponto
    apenas_numeros = re.sub(r'[^\d,.]', '', str(texto))
    if not apenas_numeros: return 0.0
    # Padroniza para ponto como separador decimal para o float
    return float(apenas_numeros.replace(',', '.'))

def formatar_br(valor):
    # Formata float para padrão brasileiro (ex: 123.456,78)
    return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')

def obter_data_brasil():
    fuso_horario = datetime.timezone(datetime.timedelta(hours=-3))
    data_hora = datetime.datetime.now(fuso_horario)
    return data_hora

def gravar_no_csv(p_original, p_promocional, p_calculado):
    arquivo_existe = os.path.isfile(ARQUIVO_RELATORIO)
    with open(ARQUIVO_RELATORIO, mode='a', newline='', encoding='utf-8-sig') as arquivo:
        writer = csv.writer(arquivo, delimiter=';')
        if not arquivo_existe:
            writer.writerow(["Data", "Hora", "Original", "Atual", "45% OFF"])
        
        agora = obter_data_brasil()
        data_str = agora.strftime("%d/%m/%Y")
        hora_str = agora.strftime("%H:%M:%S")
        
        writer.writerow([data_str, hora_str, p_original, p_promocional, p_calculado])
        print("CSV atualizado.")

# --- NOVA FUNÇÃO DE ENVIO DE DETALHES ---

def enviar_detalhes_telegram(titulo, p_orig, p_promo, p_calc, desconto_percentual, parcelamento_info):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> Sem credenciais do Telegram. Pulando envio.")
        return

    print("\nEnviando detalhes para o Telegram...")
    agora = obter_data_brasil()
    
    mensagem = (
        f"💊 *Monitoramento de Preço: {titulo}*\n"
        f"📅 {agora.strftime('%d/%m %H:%M')} (Brasília)\n\n"
        f"💰 *Preço Atual (PROMO):* R$ {p_promo}\n"
        f"💸 *Preço Original:* R$ {p_orig}\n"
        f"⬇️ *Desconto Atual:* {desconto_percentual}\n"
        f"------------------\n"
        f"🚨 *Preço c/ 45% OFF (Calculado):* R$ {p_calc}\n"
        f"------------------\n"
        f"💳 *Parcelamento:* {parcelamento_info}\n"
        f"🔗 [Link Drogasil]({URL_PRODUTO})"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    
    try:
        requests.post(url, json=payload)
        print(">> Telegram enviado!")
    except Exception as e:
        print(f">> Erro Telegram: {e}")

# --- FUNÇÃO PRINCIPAL REAJUSTADA ---

def capturar_preco():
    print("--- Iniciando Web Scraping Otimizado ---")
    driver = None
    
    preco_original_final = 0.0
    preco_promocional_final = 0.0
    parcelamento_info = "Não encontrado"
    desconto_percentual = "N/A"
    titulo_produto = "Medicamento (Título não encontrado)"

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
        time.sleep(10) # Tempo de espera reduzido para otimização
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. BUSCA POR JSON/SCHEMA.ORG (Mais confiável para preço atual)
        scripts_json = soup.find_all('script', {'type': 'application/ld+json'})
        for script in scripts_json:
            try:
                if not script.string: continue
                dados = json.loads(script.string)
                
                # Busca título do produto
                if isinstance(dados, dict) and dados.get('@type') == 'Product' and dados.get('name'):
                    titulo_produto = dados.get('name')
                
                # Busca preço atual
                if isinstance(dados, dict) and dados.get('@type') == 'Product':
                    offers = dados.get('offers')
                    if isinstance(offers, (list, dict)):
                        # Verifica se é lista ou dicionário para pegar o preço
                        offer_data = offers[0] if isinstance(offers, list) else offers
                        preco_promocional_final = float(offer_data.get('price', 0))
                    
                    if preco_promocional_final > 0: break
            except: continue

        # 2. BUSCA POR DESCONTO E PARCELAMENTO (Elementos visuais/estruturais)
        
        # Tentativa de buscar preço original (riscado)
        original_elem = soup.find('p', class_='price-tag-original')
        if original_elem:
            preco_original_final = limpar_para_numero(original_elem.text)
        elif preco_promocional_final > 0:
            # Se não encontrou o original visual, assume que o original é o promocional
            # (ou será ajustado depois com a lógica de filtro)
            preco_original_final = preco_promocional_final
            
        # Tentativa de buscar informações de parcelamento (ex: "Em até 3x sem juros")
        parcelamento_elem = soup.find(text=re.compile(r'Em até \d+x sem juros|Em até \d+x'))
        if parcelamento_elem:
            parcelamento_info = parcelamento_elem.strip()
            
        # Tentativa de buscar percentual de desconto
        desconto_elem = soup.find('span', class_=re.compile(r'tag-desconto|tag-percentual'))
        if desconto_elem:
            desconto_percentual = desconto_elem.text.strip()
            
        # 3. LÓGICA DE FILTRO DE PREÇO ORIGINAL (Recuperada da sua versão anterior)
        # Protege contra preços de referência muito altos
        if preco_promocional_final > 0 and preco_original_final > preco_promocional_final + 1.00:
            limite_aceitavel = preco_promocional_final * 1.60
            if preco_original_final > limite_aceitavel:
                print(f"Aviso: Valor original R$ {preco_original_final} ignorado (muito alto/referência).")
                preco_original_final = preco_promocional_final
        
        # 4. CÁLCULO 45% (Sempre baseado no Original)
        valor_com_45_off = preco_original_final * 0.55
        
        # Formatação
        p_orig_str = formatar_br(preco_original_final)
        p_promo_str = formatar_br(preco_promocional_final)
        p_calc_str = formatar_br(valor_com_45_off)

        print(f"RESULTADO: Original={p_orig_str} | Promo={p_promo_str} | Parcelamento={parcelamento_info}")
        
        if preco_promocional_final > 0:
            gravar_no_csv(p_orig_str, p_promo_str, p_calc_str)
            enviar_detalhes_telegram(titulo_produto, p_orig_str, p_promo_str, p_calc_str, desconto_percentual, parcelamento_info)
        else:
            print("ERRO: Bloqueio ou preço não encontrado na página.")

    except Exception as e:
        print(f"ERRO FATAL: {e}")
    
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    capturar_preco()
