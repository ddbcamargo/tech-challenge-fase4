# 🧪 Teste v0.8.4 — FFmpeg instalado pelo pip

1. Preserve seu `.env`, `.venv`, `data` e `models` ao atualizar o projeto.
2. `python -m pip install -e ".[all,test,downloader]"`
3. `python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`
4. `python -m pytest -q`
5. `python -m fase4 audioset-curated-status`
6. `python -m fase4 audioset-fetch-authorized --category Speech --limit 5`
7. Com fonte local **autorizada** e corretamente nomeada, valide um lote limitado com `--source-dir ... --download --confirm-rights`.

O `ffmpeg -version` global **não é necessário**. Os testes automatizados usam
WAVs simulados e não comprovam obtenção de vídeos online. O pacote não inclui
audios reais, credenciais ou modelos locais.
