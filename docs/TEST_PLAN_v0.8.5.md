# ✅ Plano de testes — v0.8.5: iniciar e avaliar sem preparar tudo manualmente

## 🪟 Teste imediato

1. Atualize o projeto com o ZIP, **preservando `.venv`, `.env`, `data` e `models`**.
2. No Git Bash:

   ```bash
   cd /c/GITHUB/tech-challenge-fase4
   source .venv/Scripts/activate
   python -m pip install -e ".[all,test,downloader]"
   python -m pytest -q
   python -m fase4 run
   ```

3. Aguarde a verificação dos CSVs oficiais na primeira inicialização (requer internet). Sem internet, o painel ainda deve iniciar com o baseline sintético.
4. Verifique na página a **origem identificada do modelo** (`synthetic_demo` ou `audioset_speech_reference`). **Não confundir modelo demo com AudioSet real**.
5. Aba Áudio: clique **▶️ Avaliar WAV de exemplo automaticamente (sem upload)**. Confira score, status de anomalia e persistência em SQLite.
6. Use **🎤 Ou gravar uma fala fictícia** e clique **🧠 Analisar WAV com modelo local**. A gravação deve conter somente conteúdo encenado, sem dados clínicos de terceiros.
7. Se o `.env` estiver configurado, clique em **☁️ Transcrever e analisar com Azure** e confirme transcrição/sentimento/entidades.
8. Reinicie a interface; o modelo permanece pronto e o histórico persiste.

## 📥 Treinamento oficial de verdade (somente com mídia autorizada)

- Conte ao menos 12 WAVs independentes da categoria `Speech` no `balanced_train`.
- Rode **um** comando com vídeo local ou autorização de download efetiva:

  ```bash
  python -m fase4 run --source-dir data/fontes_autorizadas --confirm-rights --limit 60
  ```

  Ou, somente se autorizado pela plataforma e titulares:

  ```bash
  python -m fase4 run --online-authorized --confirm-rights --limit 60
  ```

- Se houver 12+ WAVs importados, o `mode` muda de `synthetic_demo` para `audioset_speech_reference`.
- Se não houver, o relatório deve avisar e **não declarar treino com AudioSet**.
- As amostras para avaliação devem ser do split `eval`, não usadas no treino.

## 🔒 Checagens

- Nunca há chaves Azure, dados pessoais nem vídeos nos ZIPs de entrega.
- `ffmpeg` global no `PATH` não é obrigatório: o programa usa `imageio-ffmpeg`.
- Os testes automatizados usam mídias sintéticas ou mocks; **não** comprovam downloads do YouTube nem precisão clínica.
