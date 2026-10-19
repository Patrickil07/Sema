# Sema: Language-Learning Mode (design note)

Status: **spec capture only, nothing built.** Scope is Engine 1 only (Patrick, 2026-10-19).

## Concept

Sema's second function teaches a new language by leveraging its similarity to a language the user already knows. It relies on the linguistic principle of **intercomprehension**: instead of teaching the target language from scratch, the app acts as a cognitive bridge, mapping the structural, phonetic and vocabulary overlaps between the user's **baseline language** (e.g. Spanish) and their **target language** (e.g. French), in either direction.

The app bypasses traditional flashcard memorization by teaching **the rules of divergence** rather than individual words.

## Core architecture

The original pitch mentioned four engines; Patrick chose to keep only the first.

### Engine 1: The Lexical Distance Matrix

- At onboarding, the user enters their **native language** and any **acquired languages**.
- The app calculates the **lexical distance** (the percentage of shared vocabulary and grammar) between each known language and the target language.
- Example from the spec: a user who knows Spanish and wants to learn French (or vice versa) gets an **82% lexical similarity baseline**. The algorithm then assumes the user already has passive knowledge of thousands of words.

Open questions for later (not decisions):
- Source of the similarity figures. Published estimates vary by method; Ethnologue-style lexical similarity puts Spanish–French nearer 75% and Spanish–Italian around 82%, so the table and its source should be pinned down before build.
- Whether the baseline uses the single closest known language or combines several (e.g. Spanish + Italian toward French).
- Whether "grammar" overlap is a separate score from vocabulary or folded into one number.

## Relationship to the reader

Not yet specified. The existing reader (voices, normalize/context pipeline, browser extension) is owned by the "Sema screen reader app" thread and is not touched by this work.
