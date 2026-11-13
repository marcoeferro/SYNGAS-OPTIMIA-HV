# Diseño del evaluador adversario

## Fuentes consultadas (navegador integrado, 12/11/2026)

| Fuente | Pauta aplicada |
|---|---|
| Anthropic — *Create custom subagents* (code.claude.com/docs/en/sub-agents) | Cada subagente corre en su propio contexto, con prompt de sistema propio y herramientas restringidas; usar agentes de solo lectura para revisar. |
| Anthropic — *Demystifying evals for AI agents* (anthropic.com/engineering) | Cada prueba debe empezar en un entorno limpio y aislado; el estado compartido (incluido el historial de git de pruebas anteriores) da ventajas indebidas. Rúbricas estructuradas por dimensión, crédito parcial, ofrecer una salida «Unknown» para evitar alucinaciones, leer las transcripciones, evaluadores resistentes a trampas. |
| Anthropic — *How we built our multi-agent research system* | LLM-as-judge con rúbrica explícita (exactitud fáctica, exactitud de citas, completitud, calidad de fuentes) y salida con puntaje y aprobado/desaprobado; la revisión humana sigue siendo necesaria. |
| Anthropic — *Challenges in red teaming AI systems* | Red teaming por experto de dominio; ciclo iterativo red team / blue team. |
| OpenAI — *Advancing red teaming with people and AI* (nov. 2024) | Definir alcance y modelo de amenazas antes; composición por expertise; instrucciones, interfaces y formato de informe claros. |
| OpenAI — *Finding GPT-4's mistakes with GPT-4* (CriticGPT, jun. 2024) | Los críticos alucinan y se quejan de nimiedades; hay un equilibrio entre exhaustividad y alucinación: un humano (aquí, el agente principal) debe validar cada crítica. |
| Sharma et al. (Anthropic, 2023) — *Towards understanding sycophancy* | Los modelos tienden a complacer las creencias del usuario: no revelar quién es el autor ni que se espera aprobación. |
| Zheng et al. (2023) — *Judging LLM-as-a-Judge* (arXiv:2306.05685) | Sesgos de posición, verbosidad y autopromoción del juez. |
| Panickssery, Bowman y Feng (2024) — *LLM evaluators recognize and favor their own generations* (arXiv:2404.13076) | Un LLM favorece sus propios textos: el evaluador usa un modelo distinto del que redactó. |

## Decisiones de diseño

1. **Agente nuevo en cada ronda** (nunca se continúa uno anterior): no hereda conversación ni críticas previas.
2. **Solo lectura**: tipo `Plan` (sin Edit/Write) y prohibición explícita de modificar archivos.
3. **Sin historial**: se le prohíbe usar git y leer `docs/07_historial`, este directorio de revisión y cualquier informe de rondas anteriores; no se le dice el número de ronda ni que hubo correcciones.
4. **Modelo distinto del redactor** (Sonnet frente a Opus) para mitigar el sesgo de autopreferencia.
5. **Sin señales de complacencia**: el trabajo se presenta como el de un alumno, sin pedir aprobación.
6. **Rúbrica explícita** con 12 dimensiones y severidades (BLOQUEANTE / MAYOR / MENOR).
7. **Evidencia obligatoria**: cada observación cita ubicación y texto; puede verificar contra el código; si no puede verificar, debe decir «NO VERIFICABLE» en lugar de inventar.
8. **Triage por el agente principal** (rol humano de CriticGPT): cada observación se acepta, se acepta parcialmente o se rechaza con fundamento; las rechazadas se registran.
9. **Criterio de corte**: 10 rondas, o una ronda sin observaciones BLOQUEANTES ni MAYORES válidas tras el triage.
