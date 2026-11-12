# 🧪 Plano de testes — versão 0.8.3

## Testes automatizados (sem rede)

```bash
python -m pytest -q
```

## Testes manuais Windows/Git Bash

```bash
python -m fase4 prepare-datasets
python -m fase4 audioset-curate --seed 42
python -m fase4 audioset-fetch-authorized --category Speech --limit 5
```

A prévia deve mostrar até cinco IDs sem baixar nada. Teste a validação:

```bash
python -m fase4 audioset-fetch-authorized --category Speech --limit 5 --download
```

Sem `--confirm-rights`, deve recusar e não criar WAVs.

Com mídias de uso e download autorizados, execute **um** dos modos em
`docs/AUDIOSET_AUTOMATION.md`. Após obter 12+ WAVs, confirme:

```bash
python -m fase4 audioset-curated-status
python -m fase4 audioset-train-category Speech
python -m fase4 run
```

Valide a recuperação de uma execução parcial, IDs/intervalos, relatório de
falhas, treino separado das categorias e histórico no Streamlit.
Não misture áudios de `eval` ao treinamento. O resultado de classificação
acústica não é diagnóstico médico.

**Status de execução:** testes automatizados locais: aprovados; acesso ao
YouTube, licença dos vídeos, Azure real e Streamlit Windows: não testados.
