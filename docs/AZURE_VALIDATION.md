# ✅ Checklist de validação — Azure Speech + Language (v0.7)

## 🎯 Objetivo

Validar a ligação real entre o projeto **novo** da Fase 4 e os dois recursos
Azure criados para fins acadêmicos. Os testes automáticos não acessam a
assinatura Azure; somente o *smoke test* local fará chamadas à nuvem.

## 🔐 Pré-requisitos

- [ ] `speech-tc4` e `language-tc4` ativos, ambos Free F0.
- [ ] Arquivo `.env` local com as duas chaves, `AZURE_SPEECH_REGION=brazilsouth`
      e `AZURE_LANGUAGE_ENDPOINT=https://language-tc4.cognitiveservices.azure.com/`.
- [ ] `.env` ignorado: `git check-ignore .env` retorna `.env`.
- [ ] Credenciais **nunca** coladas em screenshots, logs, README ou commits.
- [ ] `python -m fase4 doctor` mostra `azure_speech_configured: true` e
      `azure_language_configured: true` (somente presença, não validade).
- [ ] WAV encenado de 10–20 segundos, **uma frase contínua em português**;
      16.000 Hz, mono, PCM 16-bit.

## 🪟 Testar no Git Bash

```bash
cd /c/GITHUB/tech-challenge-fase4
source .venv/Scripts/activate
python -m pip install -e ".[all,test]"
python -m unittest discover -s tests -v
python -m fase4 doctor
python -m fase4 run
```

No Streamlit, na aba **🎙️ Áudio** e no caso fictício **TC4-P001**:

1. [ ] Anexar `consulta_encenada.wav`.
2. [ ] **🔎 Inspecionar WAV localmente** e verificar o formato.
3. [ ] **☁️ Transcrever e analisar com Azure** (uma única vez).
4. [ ] Conferir que a transcrição corresponde aproximadamente ao áudio.
5. [ ] Conferir sentimento, frases-chave e entidades (podem variar; não são
        diagnósticos e algumas análises podem retornar listas vazias).
6. [ ] Abrir **📋 Histórico de análises Azure** e ver o registro salvo.
7. [ ] Reiniciar o Streamlit e conferir que o histórico continua disponível.
8. [ ] Conferir em **🚨 Alertas** somente quando houver termos literais
        sinalizados, sem considerar isso diagnóstico.

### Alternativa pelo terminal

```bash
python -m fase4 inspect-wav data/raw/consulta_encenada.wav --patient TC4-P001
python -m fase4 analyze-audio data/raw/consulta_encenada.wav --patient TC4-P001
```

A segunda chamada consome cota Azure. Não repita desnecessariamente.

## 🛡️ Testes negativos

- [ ] Sem `.env`: o botão Azure fica inativo; o restante do painel funciona.
- [ ] WAV sem fala: apresenta erro de reconhecimento, sem salvar análise Azure.
- [ ] WAV incompatível: informa que é necessário PCM16 mono 16/8 kHz.
- [ ] Chave inválida ou região errada: mensagem orientativa, sem expor segredo.
- [ ] Chamada Language com falha: não marca o fluxo como concluído.

**Não altere suas chaves reais para testar erros, nem envie gravações de
pacientes reais ao provedor.** Os casos negativos são cobertos por testes
isolados com chaves falsas. O último teste real deve ser executado apenas em
conteúdo sintético/encenado.

## 📊 Evidências para relatório

Registrar em `docs/` (sem PII, segredos ou dados reais):

- Captura do Streamlit com transcrição fictícia e análise do Language;
- Resultado da aba de histórico após reinicialização;
- Exemplo de termo sinalizado para revisão;
- Descrição do formato de entrada e dos modelos/serviços utilizados;
- Limitações: **uma fala por gravação**, resultados textuais sem diagnóstico,
  cotas F0 e ausência de avaliação clínica formal.

## 📌 Situação de validação

- **Automática:** execução dos testes locais (não consome Azure).
- **Real no Azure:** pendente até execução com `.env` privado na máquina
  Windows do desenvolvedor.

## 🧠 Complemento v0.8 — score vocal junto com o Azure

Com o modelo vocal treinado, a análise Azure do **mesmo WAV encenado** inclui o
bloco `voice` no registro persistido. O resultado possui `ml_prediction`,
`quality_flags` e `reference_mode`. Se a referência usada for sintética, o
resultado não deve ser interpretado como diagnóstico; a distribuição de
ondas artificiais não representa fala de pacientes. Consulte
[VOICE_ANOMALIES.md](VOICE_ANOMALIES.md) e [TEST_PLAN_v0.8.md](TEST_PLAN_v0.8.md).
