# Explain Simply — AutoJagaMAS in Plain English

*Written for non-technical audiences, using Malaysian business analogies.*

---

## What Does This System Do?

AutoJagaMAS is a **research team on a computer**. Instead of one person doing everything,
it has five specialists who each do one job well, and a manager who coordinates them.

You give the team a question, and they give you a researched answer — together.

---

## The Analogy: A Malaysian Law Firm

Imagine a boutique Malaysian law firm with five staff:

| Staff Member | Role in Firm | Role in AutoJagaMAS |
|---|---|---|
| **Puan Rohani** (Receptionist) | Routes every client to the right lawyer | FluidDispatcher |
| **Encik Faizal** (Managing Partner) | Decides if a junior or senior handles the file | CognitiveStack |
| **Research Team** | 3 specialists who investigate one aspect each | Botanist, Chemist, Pathologist agents |
| **The Firm's Library System** | Keeps all past cases, trust history | BrierScorer + BeliefEngine |
| **Puan Azizah** (Senior Partner) | Writes the final brief combining all findings | Synthesiser agent |

---

## The Five Components, Explained Simply

### 1. FluidDispatcher — The Receptionist at a Malaysian Government Office

When you walk into a Jabatan Kastam office, the receptionist doesn't just hand you a
number. She reads your form, looks at what department you need, and hands you a folder
with the right documents already inside.

**FluidDispatcher** does exactly this for every message the system receives:
- Reads the question
- Decides what kind of question it is (research? maintenance? urgent?)
- Loads the right context and tools into a "folder" (called a DispatchPackage)
- Passes it to the right department

*Without this: every agent would have to read everything, wasting time and money.*

---

### 2. CognitiveStack — The Department Manager Who Decides Seniority

Inside the legal firm, the managing partner reads every file that comes in and makes
one decision: "Can our junior associate handle this, or does it go to the senior partner?"

- Simple correspondence → junior associate (fast, cheap, good enough)
- Complex litigation → senior partner (slower, expensive, necessary)

**CognitiveStack** is that managing partner:
- **Qwen 3B** (local model, free to run) = junior associate — handles routine tasks
- **Claude Sonnet** (cloud API) = senior partner — handles complex reasoning
- The manager decides which one to use based on how hard the question is

*This is why the system is cost-efficient: most questions are handled locally, for free.*

---

### 3. MAS Graph — A University Research Team

Imagine a research team at Universiti Malaya studying a rare tree (Styrax sumatrana —
the "Mangliwood"):

- The **Conductor** (team leader) receives the research brief and splits it into tasks
- The **Botanist** investigates the tree's physical characteristics and density records
- The **Chemist** analyses the resin composition
- The **Pathologist** checks for disease and resistance patterns
- The **Synthesiser** (senior author) reads all three reports and writes the final paper

This is exactly how the Mangliwood swarm graph works. Each agent is a specialist.
They work in parallel. The synthesiser combines everything at the end.

*In a traditional AI chatbot, one person would try to do all five jobs at once.
A research team does it better.*

---

### 4. BDI System — The Team's Confidence Tracker

"BDI" stands for **Beliefs, Desires, Intentions** — it's a model of how an intelligent
agent tracks what it knows, what it wants, and what it plans to do.

In plain terms: **it's the team's confidence journal.**

After every research session, the system writes down:
- "When we said the resin yield was X, were we right or wrong?"
- "Our botanist's density estimate was 600 kg/m³. The external database confirmed 580–620. Good."
- "Our chemist's compound identification was wrong last time. Trust score: 0.6."

The next time a similar question comes in, the system checks these trust scores and
adjusts: if the botanist was consistently right, trust her estimate more. If the chemist
was often wrong, escalate to the cloud model for verification.

*This is called **calibrated confidence** — not just saying "I'm 70% sure",
but tracking whether that 70% claim was actually right 70% of the time.*

---

### 5. JagaShellContract — The Formal Research Brief Format

When the law firm delivers advice to a client, it doesn't send a WhatsApp message.
It sends a formal letter on letterhead, with the matter reference number, date, and
specific legal opinions clearly labelled.

**JagaShellIntent** and **JagaShellResult** are the equivalent for AutoJagaMAS:
- A structured digital envelope around every intent (task sent in) and result (answer sent out)
- Machine-readable: downstream systems can parse them without reading free text
- Ready for NemoClaw integration (a reasoning engine that cross-examines claims)

---

## The Mangliwood Demo — Why a Tree?

The **Styrax sumatrana** (Mangliwood) is a real Malaysian timber species with three
unresolved paradoxes that make it a perfect research demo:

1. **Density anomaly**: Mangliwood is denser than expected for its family — but no one
   knows why. Higher stress? Unique soil chemistry? Pathogen pressure?

2. **Resin composition**: Its benzoin resin has an unusual cinnamic acid ester ratio
   compared to the Sumatra benzoin standard. Is this a subspecies difference or a
   response to environmental conditions?

3. **Pathogen resistance**: The tree appears resistant to Phytophthora root rot, which
   devastates many related species. Is the high resin flow the mechanism?

These three paradoxes require **three different types of expertise**: botanical ecology,
organic chemistry, and forest pathology. No single AI model handles all three equally
well. A **specialist swarm** does — each agent attacks one paradox, the synthesiser
connects them.

---

## What Makes This Level 4?

The product line has four levels:

```
Level 1: JagaChatbot  — answers questions (one at a time, no tools)
Level 2: JagaRAG      — answers from documents (retrieval-augmented)
Level 3: AutoJaga     — uses tools, has memory, routes between models
Level 4: AutoJagaMAS  — multiple specialists working together (this system)
```

The jump from Level 3 to Level 4 is the difference between:
- One skilled lawyer working alone
- A full law firm with specialists, a managing partner, and a research library

For complex, multi-domain problems (like Mangliwood research), Level 4 consistently
produces better answers — more accurate, more complete, and with calibrated confidence
on each claim.

---

## Glossary for Non-Technical Readers

| Term | Plain English |
|------|---------------|
| BDI | Beliefs-Desires-Intentions — how the agent tracks what it knows and plans |
| CognitiveStack | The manager who decides: junior or senior model? |
| DispatchPackage | The folder the receptionist hands to the right department |
| FluidDispatcher | The receptionist who routes every question |
| MAS | Multi-Agent System — a team of AI specialists |
| Model Tier 1 | The junior associate (Qwen 3B, local, fast, free) |
| Model Tier 2 | The senior partner (Claude Sonnet, cloud, reasoning-capable) |
| Persona | The job description of each specialist agent |
| Profile | The category of work: RESEARCH, SIMPLE, CALIBRATION, etc. |
| Swarm | The research team — all agents working together |
