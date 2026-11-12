# 📊 Evidências — v0.8.1 (AudioSet oficial)

- **Testes automatizados:** 52 aprovados no ambiente de desenvolvimento.
- **Sem download real de trechos YouTube:** não há WAV do AudioSet embutido no
  ZIP; o código faz seleção por metadados oficiais e exige importação autorizada.
- **Treino nos testes:** executado com 12 WAVs matematicamente gerados no
  ambiente temporário de teste, vinculados a IDs CSV fictícios para verificar
  apenas a lógica de curadoria/ML. **Isso não é treinamento em AudioSet real.**
- **Treino oficial local:** fica disponível ao usuário somente depois de
  importar >=12 arquivos WAV verdadeiramente correspondentes aos IDs e
  intervalos da seleção do `balanced_train`.
- **Limitação:** `Speech` indica a presença de fala, não informa alterações
  clínicas nem a qualidade da voz. Não há métrica clínica publicada.
- **Integrações Azure e vídeo real:** precisam ser validadas no Windows,
  conforme checklist; não foram chamadas durante a suíte automatizada.
