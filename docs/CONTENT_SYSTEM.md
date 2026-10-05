# Content System

## Goal

Generate Shorts that feel like separate creator-made videos rather than variations of one template.

## Topic families

1. close-range skills
2. weapon tests
3. characters and abilities
4. maps and tactics
5. myths and experiments
6. ranked mistakes and clutches
7. underrated mechanics and discoveries

The fixed bank contains eight seeded ideas per family. When exhausted, deterministic angle variants are generated.

## Selection

The selector combines unused-topic filtering, recent history, family cooldown, phrase overlap, similarity, learned performance and deterministic tie breaking.

A family used in the recent cooldown window is penalized. This specifically prevents streaks such as:

- Close-Range Fight Mein Cover...
- Close-Range Fight Mein Jump...
- Close-Range Fight Mein Crouch...
- Close-Range Fight Mein Strafe...

Those are treated as one narrow content cluster.

## Title diversity

Gemini receives recent topic/title/hook context and is told not to recycle distinctive templates such as `Close-Range Fight Mein ...` or `Free Fire Mein ...`. A new topic must change the angle and packaging, not just the last word.

## Hook styles

Hooks are classified as question, list, warning, test_challenge, curiosity, direct_tip or statement. Analytics can learn which styles perform better once enough public data exists.

## Naturalness gate

The generator checks for formal/bookish Hindi, formulaic constructions, long spoken sentences, excessive connectors, article-like gaming language and near-duplicate topics/titles/hooks. A failed draft receives up to two targeted repair passes.

## AI-artifact cleanup

Viewer-facing text is sanitized during generation and again during description construction and final publish packaging.

Cleaned artifacts include long `---`, `___`, `===`, `***` separators, em/en dashes, markdown emphasis markers and repeated punctuation. Normal compound hyphens such as `close-range` remain valid.

## Description system

Description styles rotate among practical, question, challenge, community and simple. Style usage is persisted and becomes part of later performance learning.

## History

Each content entry records UTC time, weekday, topic, title, hook, topic family, hook style, fingerprint, source gameplay and status.

## Human review

Always review factual claims, game mechanics, pronunciation, caption timing, footage/music rights, title accuracy and thumbnail wording before publication.
