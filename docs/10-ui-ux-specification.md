# 10 UI/UX specification

Direction: a luxury productivity app with a gaming soul. Quiet, dense, legible, with one memorable element per screen, never fantasy clutter. Screenshots: `docs/screenshots/`.

## 1. Design tokens (`frontend/src/styles/app.css`)
Semantic tokens map to the brief's palette; components never use raw hex values.

| Token | Obsidian theme | Role |
|---|---|---|
| bg | #0B0F0E Obsidian | App background |
| surface | #181F1C Warm Surface | Panels |
| raised | #1F2824 | Hover, selected segments |
| coffee | #241B18 Dark Coffee | Reward surfaces (this week, insights, unlocked achievements) |
| accent | #087F5B Primary Emerald | Primary actions (white label), done states |
| accent-deep | #064E3B Deep Emerald | Active navigation, selection |
| accent-ink | #5FD3A7 | Emerald text and focus ring on dark |
| gold | #D6B46A Champagne Gold | **Earned only:** XP, levels, coins, achievements |
| ink / ink-2 / ink-3 | #F3EEE4 Soft Ivory / #C4BFB4 / #959189 | Text hierarchy (ink-3 ≥ 4.5:1 on surface) |
| danger | #E8907E | Errors, overdue |

The Ivory theme redefines the same tokens for light mode (Settings → Theme). Chart ramps were checked with the dataviz validator: the emerald heatmap ramp (#1F6650 → #8BE3C0) is monotone, single-hue and its lightest step clears 2:1 against the surface.

Measured WCAG contrast (dark theme): ink-3 5.3:1 on surface, ink-2 9.2:1, accent-ink 9.1:1, gold 8.5:1, danger 7.0:1; primary button text (white on #087F5B) 5.0:1. Ivory-theme ink-3, gold-ink and accent-ink are 5.6, 5.5 and 6.2:1 on its surface.

**Colour semantics are information:** gold appears only on things you have earned or can earn; emerald only on actions and progress state.

## 2. Typography
- **Cardo** (OFL, self-hosted WOFF subset): display: page titles, character name, level numeral, skill names. Its classical, engraved feel pairs with gold "earned" numerals.
- **DM Sans** (OFL, variable): all UI text; tabular numerals for data.
- Scale: 52/44 character name, 36 page title, 24 section, 18 subsection, 15 body, 13-12 meta. Sentence case everywhere; no all-caps labels.

## 3. Layout and navigation
- Desktop: 236 px left rail (wordmark, 7 destinations, player card), content max 1180 px, left-aligned.
- Mobile (< 768 px): sticky header (wordmark, achievements, settings) and a 5-item bottom bar (Today, Quests, Habits, Skills, Stats) with safe-area padding.
- Hash routes: `#/`, `#/quests`, `#/habits`, `#/skills[/id]`, `#/analytics`, `#/achievements`, `#/settings`.

## 4. Screens (MVP)
| Screen | Purpose | Key elements |
|---|---|---|
| Sign in / Create account | Entry | Tagline, tabbed form, inline field errors, browser time zone sent automatically |
| Command Center | Today at a glance | **Level sigil** (gold XP ring around a Cardo numeral; the one bold element), XP and daily-limit sentence, ranked top three (overdue → due today → priority), other quests for today, habits today with one-tap check-in, "This week" reward panel with recent XP ledger |
| Quest Board | Manage quests | Status segments, search, type filter, sort, archived toggle, ledger-style rows (difficulty pips ◆, due wording, skill), primary action button chosen from server `allowed_actions`, detail dialog with all actions, history, edit/archive/delete |
| Habits | Track routines | Row with check-in or numeric entry, streak, 28-day strip, 7/30-day consistency with counts, rest day, pause/resume, archive |
| Skill Tree | Competency map | Tree tabs; tiers ("Foundations", "Builds on …") from the DAG; cards with separate Practice XP (gold) and Evidence (emerald) meters; locked cards dimmed; detail dialog to add evidence and prerequisites |
| Analytics | Honest reflection | Insights with expandable basis, net XP column chart with table toggle, activity heatmap, week comparison, attribute and skill bars, metric definitions |
| Achievements | Gallery | Grouped by category; unlocked on coffee panels with gold ◆; locked dashed with ◇; hidden ones masked |
| Settings | Personalisation and data | Character (name, avatar glyphs, title, theme, time zone, day start), reward rules (read-only), password, export, sign out, delete account |

Later screens (Study Studio, Goal Roadmaps, Project Hub, Career Center, Finance, Wellness) are not built.

## 5. States
- **Loading:** shimmer skeleton blocks with an `sr-only` "Loading" status.
- **Empty:** a heading that invites the next action plus one button ("Create a quest", "New habit").
- **Error:** "That didn't load" with the server's message and Try again; mutation errors inline under the control; field errors next to inputs; unmapped field errors (e.g. time zone) are still shown (D-002).
- **Feedback:** toasts for rewards (coffee panel, gold title), info and errors; dismissible; polite live region.

## 6. Interaction rules
- Actions keep one name through the flow: "Complete" → toast "Quest complete"; "Create quest" → "Quest created".
- The only non-user-triggered motion is the sigil arc drawing to its value on load or level change. `prefers-reduced-motion` disables animations and transitions.
- Destructive actions: quest delete asks for confirmation; account deletion needs the password and typing DELETE.

## 7. Accessibility
- Every control has a visible label or `aria-label`; dialogs use native `<dialog>` (focus trap, Escape) with `aria-labelledby`.
- Visible 2 px focus ring (emerald ink); skip link to main content.
- Habit check-ins are `role="checkbox"` with `aria-checked`; meters use `role="meter"` with values; the sigil has a text alternative ("Level 2. 50 of 183 XP into this level.").
- Colour is never the only signal: difficulty uses pip counts, statuses use words, the heatmap has hover text and the XP chart has a table view.
- E2E tests locate elements by role and accessible name, which fails if labels regress.
- Not yet done: automated axe scan, screen-reader walkthrough, high-contrast/forced-colours check.
