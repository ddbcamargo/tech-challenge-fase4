# 📋 Resultados registrados — v0.8.2

- Regra do projeto: datasets do enunciado têm prioridade.
- Fonte: índices oficiais do Google AudioSet v1 (`balanced_train`, `eval` e
  catálogo de classes), sem afirmar acesso aos WAVs originais.
- Cotas padrão no projeto: treino Speech 24, Breathing 16, Cough 16, Wheeze
  16, Silence 8; avaliação Speech 8 e demais 6 cada.
- Estratégia: preferência por rótulos menos ambíguos, hash estável com
  semente, deduplicação por ID de vídeo e separação entre treino/avaliação.
- Resultado medido localmente: **59 testes automatizados aprovados**
  sobre **índices simulados e WAVs artificiais locais**, com treinamentos e inferências para
  comprovar funcionamento. Não equivalem a resultados com AudioSet real.
- Limites: rótulos acústicos não são diagnósticos; sem avaliação clínica,
  sem verificação automática da procedência dos vídeos/áudios e sem melhoria
  comprovada de desempenho até importar amostras reais independentes.

Veja `docs/TEST_PLAN_v0.8.2.md` para reprodução e checklist no Windows.
