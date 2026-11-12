# ✅ Validação local da versão 0.9.0

Data da verificação: 06/11/2026. Ambiente de construção Linux com Python 3.13.

## Testes automatizados

```text
python -m pytest -q
80 passed
```

Incluídos testes de regressão de versões anteriores e novos testes de
análise de movimentação inventada, relatório de postura simulado, Azure com
stubs, correlação multimodal, isolamento por paciente, prevenção de duplicatas,
acréscimo de modalidades e migração do SQLite anterior.

## Smoke test de CLI

```text
python -m fase4 --db /tmp/tc4_v090_smoke.sqlite3 init
Banco preparado: 25 novos pacientes fictícios (até 25 no total)

python -m fase4 --db /tmp/tc4_v090_smoke.sqlite3 scan all --patient TC4-P001
3 eventos identificados (duplicatas ignoradas na persistência)
```

Foi observada evidência persistida `MULTIMODAL_REVIEW` com modalidades
`movement` e `prescription`, referenciando três alertas-fonte e mantendo
`observed_at` dos dados inventados e `recorded_at` da execução demonstrativa.

## Limites da validação

- Azure Speech/Language: somente testes com SDK simulado. Não há credenciais
  disponíveis neste ambiente, portanto não foi feita chamada real.
- MediaPipe: lógica e relatórios testados com pose simulada; não houve
  inferência com MP4 real no ambiente de construção.
- Streamlit: módulos compilados, mas a execução interativa deve ser verificada
  no ambiente do usuário com Streamlit instalado.
- Não há avaliação clínica nem sincronização com dispositivos hospitalares.
