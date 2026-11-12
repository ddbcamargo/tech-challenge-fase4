# 📄 Relatório técnico — Tech Challenge 4

## 1. Objetivo

Protótipo acadêmico para análise de vídeo, áudio e dados clínicos de um cenário
hospitalar fictício, integrando evidências para revisão humana. Os objetivos e
entregáveis seguem as páginas 2–4 do enunciado FIAP.

## 2. Arquitetura e fluxo multimodal

Monólito modular, camadas domínio/aplicação/infraestrutura/interfaces. As
observações são produzidas por importação de dados históricos, gravação
encenada ou vídeo autorizado. O serviço de aplicação detecta desvios, grava
resultados e gera alertas. Uma correlação por paciente fictício e por
**momento de inserção no protótipo** agrega modalidades distintas na janela
simulada de 30 minutos. Alertas ficam no SQLite até revisão humana.

## 3. Modelos e métodos

- **Sinais vitais:** histórico PhysioNet Challenge 2019, outliers com mediana
  e MAD por métrica e por fonte, sem referência clínica.
- **Prescrições:** transições fictícias de dose/frequência/unidade.
- **Movimentação:** trajetória fictícia e regras simples de deslocamento e
  inatividade, sem sensores reais.
- **Áudio:** Azure Speech-to-Text (reconhecimento pt-BR de fala curta), Azure
  AI Language (sentimento, frases-chave, entidades); termos críticos por regras
  e indicadores locais de energia/pausa/saturação/ritmo. As regras de texto preservam
  o trecho literal, a categoria e os offsets, e vinculam o alerta ao ID do
  processamento de áudio no SQLite. Não diagnostica.
- **Vídeo:** MediaPipe Pose Landmarker pré-treinado, ângulos de joelho/cotovelo,
  desvio estatístico robusto relativo ao próprio vídeo; relatório JSON.
- **AudioSet:** dataset sugerido pelo enunciado; índices e categorias servem
  como catálogo de eventos sonoros. Não usado como corpus clínico rotulado.

## 4. Evidências reproduzíveis

- Executar `python -m pytest -q` e registrar número e saída da suíte.
- Executar `python -m fase4 doctor` sem mostrar chaves.
- Carregar PSV da PhysioNet, avançar replay e exportar JSON de alertas.
- Gravar uma frase fictícia, transcrever no Azure e capturar o resultado (sem
  informações de pacientes reais).
- Analisar MP4 autorizado, exportar relatório JSON e indicar frames válidos.
- Exibir alerta multimodal e fluxo de revisão humana no dashboard.

## 5. Resultados atualmente verificados

A implementação foi testada com suíte automatizada e serviços simulados. Há
cobertura de regras, persistência, migração de banco, cenário de movimentação,
relatório de vídeo simulado e fusão de alertas, além das integrações Azure
substituídas por stubs. **A integração Azure Speech + Language foi executada pelo usuário no Windows,
com transcrição, sentimento `mixed`, seis expressões-chave e duas entidades.**
O vídeo MP4 com MediaPipe ainda requer validação real no ambiente do usuário.

**Preencher após teste local:**

| Evidência | Resultado real | Observações |
|---|---|---|
| Azure Speech transcreveu fala fictícia | **Confirmado em teste manual do usuário** | Texto de dores nas mãos/punhos |
| Azure Language retornou sentimento/termos | **Confirmado em teste manual do usuário** | `mixed`, frases-chave e entidades |
| MediaPipe identificou quadros com pose | *Pendente* | |
| Relatório de desvios em vídeo | *Pendente* | |
| Alertas PhysioNet e alterações fictícias | *Pendente validação visual* | |
| Correlação multimodal exibida e revisada | *Pendente validação visual* | |

## 6. Limitações

Não há telemetria em tempo real, prontuário hospitalar nem envio a profissionais
reais. Os eventos de pacientes fictícios são associados a dados públicos **sem
correspondência com indivíduos do PhysioNet**. A fusão é uma simulação de
registro, não prova de simultaneidade clínica. Medições acústicas e outliers
estatísticos não classificam disartria, fadiga, patologias nem risco médico.
O MediaPipe pode não estimar postura em casos de oclusão ou baixa iluminação.
Não há validação clínica, nem precisão, recall ou falsos positivos calculados
com base clínica rotulada.

## 7. Próximas melhorias (não entregues nesta versão)

Avaliação quantitativa com bases rotuladas adequadas, validação da transcrição
em amostras reais autorizadas, rótulos confiáveis de anormalidade motora,
sensorização de movimento, processamento contínuo e controle de acesso.
