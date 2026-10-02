# Bloom's taxonomy and learning objectives

Uses the revised taxonomy (Anderson & Krathwohl, 2001). Levels are cumulative: learners
need the lower ones to do the higher ones.

## The six levels

| Level | Learners can... | Verbs | Assess with |
|---|---|---|---|
| **Remember** | recall facts and terms | define, identify, list, name, recall, recognize, state | MCQ, matching, labelling, fill-in |
| **Understand** | explain ideas in their own words | classify, compare, explain, interpret, paraphrase, summarize, give examples | MCQ asking "why", explain-in-your-words, concept sorting |
| **Apply** | use a procedure in a given situation | apply, calculate, demonstrate, implement, rewrite, solve, use | Scenario MCQ, worked problems, simulations, short tasks |
| **Analyze** | break a situation into parts and find relationships or causes | analyze, categorize, diagnose, differentiate, examine, troubleshoot | Case studies, "what went wrong" scenarios, error spotting |
| **Evaluate** | judge against criteria and justify the judgement | assess, critique, defend, judge, justify, prioritize, recommend | Critiques, comparisons with justification, peer review with a rubric |
| **Create** | combine parts into something new and coherent | build, compose, design, develop, plan, produce, propose, write | Projects, portfolios, designs, plans, graded with a rubric |

`scripts/course_tool.py` holds the full verb list. Some verbs sit at two levels
(*compare*: Understand or Analyze; *select*: Remember or Evaluate). In that case the
declared level and the task decide. "Compare two definitions" is Understand; "compare two
vendor proposals to find the cheaper long-term option" is Analyze.

## Knowledge dimension

Record what kind of knowledge each objective is about. It shapes how you teach it:

| Type | Is about | Teach with |
|---|---|---|
| Factual | terms, details, facts | Chunked lists, retrieval practice, flashcards |
| Conceptual | categories, principles, models, how things relate | Examples and non-examples, diagrams, analogies |
| Procedural | how to do something, techniques, when to use them | Worked examples, then practice with fading support |
| Metacognitive | awareness of your own thinking, strategy choice | Reflection prompts, self-assessment checklists |

## Writing an objective

Use **ABCD**, at least the B and ideally the C and D:

- **Audience**: who (often implied by the course: "Learners will...")
- **Behavior**: one observable verb + object. "Diagnose why a prompt failed"
- **Condition**: given what, or in what situation. "Given a prompt and its output"
- **Degree**: how well. "Naming the missing part in 4 of 5 cases"

> *Given a prompt and its off-target answer, diagnose which of the four parts was missing,
> correctly in 4 of 5 cases.*

Rules:
- **One verb per objective**, so it can be assessed on its own. Split "explain and apply".
- **Observable verbs only.** Never *understand, know, learn, appreciate, be aware of,
  be familiar with, grasp, master, explore*. Ask "what would I see them do if they
  understood?" and write that verb instead.
- **Course outcomes** describe what learners do after the course, usually at Apply or
  above. **Module objectives** are the steps that build up to them.
- Write 2-6 course outcomes and 2-5 objectives per module. More than that means the course
  or the module is too big.

| Weak | Strong |
|---|---|
| Understand budgeting | Build a monthly budget from three months of bank statements |
| Know the GDPR principles | Classify five data-handling scenarios as compliant or not, citing the principle |
| Learn Python loops | Write a loop that totals the values in a list |
| Be aware of phishing | Identify the warning signs in a suspicious email |

## Balancing levels across a course

- Intro courses lean lower (more Remember and Understand) but should still reach Apply.
  Learners remember what they use.
- No more than about 60% of objectives at Remember and Understand. The checker warns above
  that.
- Climb inside each module: a module usually goes Remember or Understand, then Apply, then
  one higher step.
- Every outcome needs at least one objective at its own level. An Evaluate outcome with
  only Understand objectives under it is never practised.

## Matching assessment to level

The item has to make learners *do the verb*:

- **Remember / Understand**: direct MCQ, matching and short answer work.
- **Apply / Analyze**: put the learner in a situation. Scenario stems ("A customer
  says... What should you do first?"), data to interpret, an error to find. A plain
  recall MCQ under an Apply objective under-tests it.
- **Evaluate / Create**: need a performance: a critique, a recommendation with
  justification, a design, a plan. Grade with a rubric. Choice items can't show creation.

Question stems by level:
- Remember: "What is...?", "Which of these is...?"
- Understand: "Why does...?", "Which example shows...?", "What is the main idea of...?"
- Apply: "Given ..., what would you do?", "Use ... to calculate..."
- Analyze: "What is the most likely cause of...?", "Which part of ... explains...?"
- Evaluate: "Which option is best for ..., and why?", "Critique ... against ..."
- Create: "Design/plan/write a ... that ..."
