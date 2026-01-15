# Deckbuilding Heuristics & Rules

This document captures deckbuilding knowledge, formulas, and rules of thumb discovered during research and development. These inform the deck engine's decision-making.

## Format Rules (Commander/EDH)

### Hard Constraints
- **Deck size**: Exactly 100 cards including commander
- **Singleton**: Maximum 1 copy of any card except basic lands
- **Color identity**: All cards must match commander's color identity (including mana symbols in text)
- **Legality**: All cards must be legal in Commander format (ban list enforced)
- **Commander eligibility**: Legendary creature OR explicit "can be your commander" text

### Companion Rules
- If using companion, it counts toward the 100 cards
- Companion deck-building restriction applies to entire 100-card deck
- No sideboard in Commander

## Land Calculation

### Baseline Formula (Riftgate Calculator)
**Source**: https://riftgate.com/pages/mtg-land-calculator

**Base counts by deck size**:
- 40 cards → 17 lands (42.5%)
- 60 cards → 24 lands (40%)
- **100 cards → 37 lands (37%)**

**Color distribution**:
```
lands_per_color = round((total_lands × color_pips) / total_pips)
```
- Minimum 1 land per color used
- Adjust for rounding to hit exact target (decrement colors with >1 land)

### Adjustments (To Be Implemented)

**Ramp adjustment**:
- Subtract ~2 lands per 10 ramp sources
- Ramp sources: cards with CMC ≤ 3 that produce mana or fetch lands
- Examples: Sol Ring, Arcane Signet, Rampant Growth, mana dorks

**Curve adjustment**:
- Low curve (avg CMC < 2.5): -2 lands (35 total)
- High curve (avg CMC > 3.5): +1 to +2 lands (38-39 total)
- Calculate average CMC excluding lands

**Draw density adjustment**:
- High card draw (10+ draw sources): Can run fewer lands safely
- Consider: -1 land if 10+ card draw spells

**Color intensity weights**:
- Heavy devotion (e.g., WWW in cost): Weight pips more heavily
- Splash colors (1-2 cards): Minimum sources, consider utility lands
- Double pips in early game (≤3 CMC): Increase that color's land count

**Utility lands**:
- Allocate 10-15% of land base (4-6 lands) to non-basics with abilities
- Examples: Strip Mine, Reliquary Tower, Command Tower, dual lands

## Card Role Distribution

### Standard Template (MVP)
Based on common EDH deck structure:

| Role | Count | Percentage | Purpose |
|------|-------|------------|---------|
| Lands | 37 | 37% | Mana production |
| Ramp | 10 | 10% | Accelerate mana |
| Draw | 10 | 10% | Card advantage |
| Removal | 10 | 10% | Interaction/answers |
| Synergy/Theme | 25 | 25% | Commander strategy |
| Win Conditions | 5 | 5% | Game-ending cards |
| Flex/Utility | 3 | 3% | Meta calls, protection |

**Total**: 100 cards

### Role Definitions

**Ramp**:
- CMC ≤ 3 preferred
- Produces or fetches mana
- Examples: Sol Ring, Cultivate, land ramp spells, mana rocks

**Draw**:
- Generates card advantage
- Repeatable sources valued higher
- Examples: Rhystic Study, Consecrated Sphinx, wheels, cantrips (if synergistic)

**Removal**:
- Destroys/exiles threats
- Mix of spot removal and board wipes
- At least 2-3 board wipes in slower decks
- Examples: Swords to Plowshares, Cyclonic Rift, Wrath of God

**Synergy/Theme**:
- Cards that interact with commander's strategy
- Tribe members (tribal decks)
- Keyword support (voltron, spellslinger)
- Archetype-specific enablers

**Win Conditions**:
- Cards that directly end the game
- Should be resilient or hard to interact with
- Examples: Craterhoof Behemoth, Thassa's Oracle, infinite combos

**Flex/Utility**:
- Meta-dependent choices
- Protection for commander
- Graveyard hate, artifact/enchantment removal
- Recursion

## Mana Curve Guidelines

### Target Distribution (CMC)
```
0-1 CMC:  10-12 cards (10-12%)  - Fast mana, 1-drops
2 CMC:    12-15 cards (12-15%)  - Ramp, early plays
3 CMC:    15-18 cards (15-18%)  - Peak of curve
4 CMC:    10-12 cards (10-12%)  - Powerful effects
5 CMC:    8-10 cards  (8-10%)   - High-impact spells
6+ CMC:   5-8 cards   (5-8%)    - Bombs, finishers
```

**Average CMC target**: 2.5 - 3.5 (excluding lands)

### Curve Principles
- Front-load interaction and ramp (low CMC)
- Peak at 3 CMC for versatility
- High CMC should be game-ending or very high value
- Commander CMC affects curve (high-cost commander = lower curve)

## Archetype-Specific Templates

### Tribal
- **Tribe members**: 30-35 cards minimum
- **Lords/anthems**: 5-8 cards (tribal synergy)
- **Ramp**: 8-10 (slightly lower, creatures provide bodies)
- **Draw**: 10 (tribal payoffs may provide draw)
- **Removal**: 8-10
- **Lands**: 37

### Spellslinger
- **Instants/sorceries**: 30-40 spells
- **Spell payoffs**: 8-12 (Talrand, Storm, prowess)
- **Ramp**: 10-12 (mana-hungry)
- **Draw**: 8-10 (cantrips within spell count)
- **Removal**: Within spell count
- **Lands**: 35-37

### Sacrifice/Aristocrats
- **Sacrifice fodder**: 15-20 creatures
- **Sacrifice outlets**: 6-8 (free activation preferred)
- **Death triggers**: 8-10 (Blood Artist effects)
- **Recursion**: 8-10 (return creatures from graveyard)
- **Ramp**: 10 (sacrifice-based ramp viable)
- **Removal**: 8-10
- **Lands**: 37

### Goodstuff/Generic
- Use standard template
- Focus on universal staples
- High individual card quality
- Flexible interaction

## Power Level Considerations (Future)

### Budget Tiers
- **Budget (<$50 total)**: Exclude reserved list, expensive staples
- **Mid ($50-$200)**: Mix of staples and budget alternatives
- **Optimized ($200-$500)**: Include fast mana, dual lands
- **cEDH (>$500)**: No budget constraints

### Power Level Indicators
- **Casual (1-4)**: Slower, thematic, minimal combos
- **Focused (5-7)**: Optimized strategy, some combos
- **Competitive (8-10)**: Fast mana, tutors, efficient combos

## Card Inclusion Heuristics

### Auto-Include (if in color identity)
- Sol Ring (unless very low artifact synergy)
- Commander's Sphere / Arcane Signet (color-fixing ramp)
- Efficient removal (Path to Exiles, Generous Gift, etc.)
- Card draw staples (Rhystic Study, Sylvan Library if budget allows)

### Anti-Synergy Detection
- Avoid cards that conflict with commander strategy
- Examples: Mass land destruction in creature-heavy deck, graveyard hate in reanimator
- Check oracle text for negative interactions

### Synergy Detection (MVP Approach)
- **Keyword matching**: Search oracle text for commander's keywords
- **Tribe matching**: If commander has creature type, prioritize that type
- **Mechanic matching**: Pattern match common mechanics (sacrifice, tokens, +1/+1 counters, etc.)

## Legality Checks

### Validation Order
1. **Commander eligibility**: Check type line + oracle text
2. **Color identity**: Extract from mana cost + oracle text + color indicator
3. **Singleton**: Ensure ≤1 copy (except basics)
4. **Format legality**: Check legalities.commander field
5. **Deck size**: Exactly 100 cards
6. **Ban list**: Cross-reference current EDH ban list

### Color Identity Rules
- Includes all mana symbols in mana cost
- Includes all mana symbols in oracle text (even in reminder text)
- Includes color indicator (for cards with no mana cost)
- Excludes mana symbols in flavor text
- Hybrid mana counts as both colors
- Phyrexian mana counts as its color (can be paid with life, but adds to identity)

## Export Formats

### Text Format
```
Commander:
1 [Commander Name]

Lands: (37)
1 [Land Name]
...

Ramp: (10)
1 [Ramp Card]
...
```

### CSV Format
```csv
Quantity,Name,Type,CMC,Role,Price
1,CommanderName,Legendary Creature,4,Commander,5.00
1,Sol Ring,Artifact,1,Ramp,2.50
...
```

## Research Sources

### Consulted Resources
- **Riftgate MTG Land Calculator**: https://riftgate.com/pages/mtg-land-calculator
  - Baseline land counts and proportional distribution
  - Added: 2026-01-14

### To Research
- EDHREC average deck compositions by archetype
- Frank Karsten mana base mathematics (ChannelFireball articles)
- Command Zone deck-building philosophy
- cEDH Database optimization techniques
- Professor's deck techs (Tolarian Community College)

## Updates

**2026-01-14**: Initial document creation
- Added Riftgate land calculator methodology
- Defined standard role distribution template
- Established archetype-specific templates
- Documented color identity and legality rules
