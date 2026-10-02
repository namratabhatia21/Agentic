# course.json: the course blueprint

One JSON file holds the course structure, the alignment and all assessment items. Lesson
text lives in Markdown files that `file` points to. Paths are relative to `course.json`.
`scripts/course_tool.py` reads this file to check, map, export and preview the course.

A complete, passing example is in [../assets/example-course/](../assets/example-course/).
Its sources are illustrative.

## Top level

| Field | Type | Notes |
|---|---|---|
| `title` | string | Required |
| `subtitle` | string | One line: length and who it's for |
| `sources` | list | `{id, title, location}`. IDs (S1, S2...) are what lessons cite |
| `audience` | object | `persona`, `prior_knowledge`, `needs` |
| `format` | object | `delivery` (self-paced / live / blended), `total_minutes`, `platform`, `model` (ADDIE / SAM) |
| `outcomes` | list | Course outcomes: `{id, text, bloom}`. IDs like CO1 |
| `modules` | list | See below |
| `final_assessment` | list | Assessment items (same shape as module items) |

## Module

| Field | Type | Notes |
|---|---|---|
| `id`, `title` | string | IDs like M1 |
| `objectives` | list | `{id, text, bloom, knowledge, supports}`. `supports` lists outcome IDs. `knowledge` is factual / conceptual / procedural / metacognitive |
| `lessons` | list | `{id, title, minutes, objectives, media, file}`. Add `file` once the lesson is written |
| `activities` | list | `{id, title, type, minutes, objectives, instructions}`. `type`: practice, case study, discussion, reflection, project... |
| `assessment` | list | Formative items for this module |

## Assessment item

Common fields: `id`, `type`, `objective` (one ID) or `objectives` (list), `bloom`,
`stem`, and optionally `minutes` (default 1).

| `type` | Extra fields |
|---|---|
| `mcq` | `options` (list), `answer` (index from 0), `feedback` (list, one per option) |
| `multi` | `options`, `answer` (list of indexes), `feedback` (list) |
| `truefalse` | `answer` (true / false), `feedback` (string) |
| `short` | `answer` (list of accepted answers), `feedback` (string) |
| `essay`, `project` | `rubric`: list of `{criterion, excellent}`, or a string pointing to the rubric file |

`bloom` is one of `remember`, `understand`, `apply`, `analyze`, `evaluate`, `create`.

## ID conventions

`CO1` for outcomes; `M1` for modules; `M1.1` for objectives; `M1.L1` for lessons;
`M1.A1` for activities; `M1.Q1` for items; `F1` for final items. IDs must be unique across
the whole file.

## Minimal skeleton

```json
{
  "title": "",
  "subtitle": "",
  "sources": [{"id": "S1", "title": "", "location": ""}],
  "audience": {"persona": "", "prior_knowledge": "", "needs": ""},
  "format": {"delivery": "self-paced", "total_minutes": 60, "platform": "", "model": "ADDIE"},
  "outcomes": [{"id": "CO1", "text": "", "bloom": "apply"}],
  "modules": [
    {
      "id": "M1",
      "title": "",
      "objectives": [
        {"id": "M1.1", "text": "", "bloom": "understand", "knowledge": "conceptual", "supports": ["CO1"]}
      ],
      "lessons": [{"id": "M1.L1", "title": "", "minutes": 8, "objectives": ["M1.1"], "media": "text"}],
      "activities": [],
      "assessment": [
        {"id": "M1.Q1", "type": "mcq", "objective": "M1.1", "bloom": "understand", "stem": "",
         "options": ["", "", "", ""], "answer": 0, "feedback": ["", "", "", ""]}
      ]
    }
  ],
  "final_assessment": []
}
```
