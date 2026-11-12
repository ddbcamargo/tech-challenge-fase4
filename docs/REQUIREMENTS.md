# ✅ Matriz do enunciado — Fase 4 (FIAP)

Referência: `IADT - Fase 4 - Tech challenge.pdf`, páginas **2–4**.
O enunciado pede análise multimodal e alertas, **não** treinamento obrigatório
de modelo de Machine Learning do zero.

| Exigência literal/resumo | Implementação | Validação pendente |
|---|---|---|
| Processar vídeos de sessões de fisioterapia/cirurgias | MP4 + MediaPipe Pose Landmarker, ângulos, desvio MAD e relatório JSON | Testar com MP4 real autorizado, observar qualidade da pose e falsos alertas; não cobre análise cirúrgica |
| Identificar movimentos fora do esperado | Desvios estatísticos de quatro articulações contra o próprio vídeo | Não é classificação clínica de erros de procedimento |
| Áudios de consultas, alterações vocais | WAV encenado, indicadores de silêncio/energia/clipping e ritmo aproximado | Verificar representatividade; não diagnostica disartria, cansaço ou dispneia |
| **Azure Speech-to-Text** | Speech SDK, pt-BR, uma fala curta | Teste real com chaves locais, cota F0 e fala encenada |
| **Azure Text Analytics** | Azure AI Language — sentimento, frases-chave, entidades; regras para termos críticos | Teste real com chave/endpoint; não confundir sentimento e gravidade clínica |
| Anomalias em sinais vitais | PhysioNet Challenge 2019, replay + regra robusta por série | Testar mais pacientes/fontes e medir alertas falsos |
| Alterações em prescrições | Regras de dose, unidade, frequência; dados inventados | Ampliar cenários sem sugerir condutas clínicas |
| Padrões de movimentação na internação | Trajetória espacial inventada, inatividade e deslocamento | Não é dado capturado por sensor real |
| Alertas automáticos e equipe médica | SQLite: alerta, evidência, estado `pending_review`/`reviewed`/`dismissed` | Entrega demonstrativa no painel, sem notificações clínicas externas |
| Análise/fusão multimodal | Associação por caso, modalidade e janela de **registro** local de 30 min | Não demonstra causalidade médica ou monitoramento ao vivo |
| Usar serviços gerenciados em nuvem | Azure Speech + Azure Language | Validar no ambiente Windows com suas credenciais |
| Entregáveis | Código, relatório técnico, roteiro de demo até 15 min | Capturar resultados reais, gravar/publicar vídeo demonstrativo |

### Fontes prioritárias (página 4)

1. **PhysioNet** para sinais vitais; amostra oficial importada por arquivo PSV.
2. **Google AudioSet** para rótulos e catálogo de eventos sonoros; não há
   áudio de consulta clínica rotulado nem obrigação de baixar YouTube.
3. Gravação encenada para **demonstração de Speech-to-Text** e vídeo
   autorizado para **fisioterapia**, pois o enunciado não fornece arquivos
   de consulta ou dataset de vídeo específico.

Nenhum código, banco de pacientes ou arquivo clínico da Fase 3 foi reutilizado.
