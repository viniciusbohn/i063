"""
Script para baixar e salvar o CSV do Google Sheets para verificação
"""
import pandas as pd
from urllib.parse import quote
import sys

def download_sheets_data():
    """
    Baixa dados da aba "Base | Atores MG" do Google Sheets e salva como CSV
    """
    try:
        sheet_id = "104LamJgsPmwAldSBUOSsAHfXo4m356by44VnGgk2avk"
        sheet_name = "Base | Atores MG"
        
        print(f"Baixando dados da aba: {sheet_name}")
        print(f"Sheet ID: {sheet_id}")
        
        # Método 1: Tenta com a URL de export CSV direta usando o nome da aba
        try:
            encoded_sheet_name = quote(sheet_name, safe="")
            sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
            print(f"\nTentando URL: {sheet_url}")
            
            # Tenta diferentes encodings
            df = None
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    print(f"Tentando encoding: {encoding}")
                    df = pd.read_csv(sheet_url, encoding=encoding)
                    print(f"✓ Sucesso com encoding: {encoding}")
                    break
                except Exception as e:
                    print(f"✗ Falhou com encoding {encoding}: {str(e)}")
                    continue
            
            if df is None:
                raise Exception("Não foi possível baixar com nenhum encoding")
                
        except Exception as e:
            print(f"\nErro no método 1: {str(e)}")
            # Método 2: Tenta com export direto
            try:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                print(f"\nTentando método alternativo: {sheet_url}")
                df = pd.read_csv(sheet_url, encoding='utf-8')
            except:
                df = pd.read_csv(sheet_url, encoding='latin-1')
        
        # Remove linhas completamente vazias
        df = df.dropna(how='all')
        
        # Remove espaços dos nomes das colunas
        df.columns = df.columns.str.strip()
        
        # Remove linhas onde a primeira coluna está vazia
        if len(df) > 0 and len(df.columns) > 0:
            primeira_col = df.columns[0]
            if primeira_col in df.columns:
                mask = df[primeira_col].notna() & (df[primeira_col].astype(str).str.strip() != '')
                df = df[mask]
                df = df[~df[primeira_col].astype(str).str.contains('^name$|^Name$|^NAME$', case=False, na=False, regex=True)]
        
        # Salva o CSV
        output_file = "dados_base_atores_mg.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✓ CSV salvo em: {output_file}")
        
        # Mostra informações sobre o DataFrame
        print(f"\n{'='*60}")
        print(f"INFORMAÇÕES DO DATASET")
        print(f"{'='*60}")
        print(f"Total de linhas: {len(df)}")
        print(f"Total de colunas: {len(df.columns)}")
        print(f"\nNomes das colunas:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")
        
        print(f"\n{'='*60}")
        print(f"PRIMEIRAS 5 LINHAS:")
        print(f"{'='*60}")
        print(df.head().to_string())
        
        print(f"\n{'='*60}")
        print(f"VERIFICAÇÃO DE COLUNAS ESPECÍFICAS:")
        print(f"{'='*60}")
        
        # Verifica coluna de nome
        colunas_nome = [col for col in df.columns if 'nome' in col.lower() or 'name' in col.lower()]
        print(f"\nColunas com 'nome' ou 'name': {colunas_nome}")
        if colunas_nome:
            for col in colunas_nome:
                print(f"\n  Coluna '{col}':")
                print(f"    Primeiros valores: {df[col].head(10).tolist()}")
        
        # Verifica coluna de região
        colunas_regiao = [col for col in df.columns if 'regiao' in col.lower() or 'região' in col.lower() or 'sebrae' in col.lower()]
        print(f"\nColunas com 'regiao', 'região' ou 'sebrae': {colunas_regiao}")
        if colunas_regiao:
            for col in colunas_regiao:
                print(f"\n  Coluna '{col}':")
                print(f"    Primeiros valores: {df[col].head(10).tolist()}")
        
        return df
        
    except Exception as e:
        print(f"\n❌ Erro ao baixar dados: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    df = download_sheets_data()
    if df is not None:
        print(f"\n✓ Processo concluído com sucesso!")
    else:
        print(f"\n✗ Falha ao baixar dados")
        sys.exit(1)

