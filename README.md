# SmartStock Analytics

Versão final corrigida do dashboard.

## Correções desta versão

- Leitura robusta de planilhas com várias lojas/blocos.
- Correção de datas digitadas incorretamente.
- Filtro de lojas.
- Filtro por Data inicial e Data final.
- Gráficos temporais agregados por data para evitar distorções.
- Planilha anonimizada incluída na pasta `data`.

## Como executar

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

O sistema carrega automaticamente a planilha da pasta `data`.
Também é possível enviar outra planilha pela barra lateral.
