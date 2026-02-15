# 9 Star Ki Reference

## Overview

9 Star Ki is a Japanese adaptation of Chinese Feng Shui astrology based on the Lo Shu magic square. It calculates three numbers from a birth date that describe personality, relationships, and life cycles.

## The Three Numbers

| # | Name | Meaning |
|---|------|---------|
| **1st (Year Ki)** | Essence | Invisible to self — the iceberg below water. Governs the parts of ourselves we can't see. Works in conjunction with natal chart. |
| **2nd (Month Ki)** | Emotion | Internal processing, the heart, qualities/abilities, strengths/weaknesses, potential trauma triggers. Under stress, we resort to the **shadow qualities** of this number. |
| **3rd Ki** | Life Path | How people see you externally + contextualizes the nodes, career, societal roles, larger lessons, the mirror we must see through on our journey. |

### Psychological Integration
- **Essence** weaves with the natal chart's hidden elements
- **Emotion** connects to Moon themes and attachment patterns  
- **Life Path** connects to nodal story and career arc

## The Lo Shu Square

The magic square where all rows, columns, and diagonals sum to 15:

```
4 | 9 | 2      SE | S  | SW
---------      -----------
3 | 5 | 7  →   E  | ☯  | W  
---------      -----------
8 | 1 | 6      NE | N  | NW
```

Palace numbers are FIXED positions. Ki numbers FLY through them.

## The Nine Stars

| Ki | Trigram | Name | Element | Qualities |
|----|---------|------|---------|-----------|
| 1 | ☵ | Water (Kan) | Water | Adaptable, deep, mysterious, diplomatic |
| 2 | ☷ | Earth (Kun) | Earth | Nurturing, supportive, receptive, devoted |
| 3 | ☳ | Thunder (Zhen) | Wood | Pioneering, enthusiastic, impulsive, direct |
| 4 | ☴ | Wind (Xun) | Wood | Gentle, penetrating, communicative, flexible |
| 5 | ☯ | Center (Tai Chi) | Earth | Powerful, controlling, central, transformative |
| 6 | ☰ | Heaven (Qian) | Metal | Authoritative, leader, father, structured |
| 7 | ☱ | Lake (Dui) | Metal | Joyful, charming, reflective, expressive |
| 8 | ☶ | Mountain (Gen) | Earth | Still, contemplative, stubborn, transitional |
| 9 | ☲ | Fire (Li) | Fire | Illuminating, visible, passionate, clarity |

## Calculating Natal Ki

### Year Ki
- Changes on **February 4** (Lichun/Spring Begins), not January 1
- Cycles: 9 → 8 → 7 → 6 → 5 → 4 → 3 → 2 → 1 → 9...
- Reference: 2026 = Ki year 1

### Month Ki  
- Changes mid-month on specific dates (varies by month)
- Starting month (February) depends on year Ki group:
  - Years 1, 4, 7 → February = 8
  - Years 2, 5, 8 → February = 5
  - Years 3, 6, 9 → February = 2

### Third Ki
- Derived from Year + Month using Flying Star Lo Shu method
- Put Month Ki in center, find which palace Year Ki occupies

## Flying Star Method

When a number is placed in the center, all other numbers shift according to the flying sequence:

```
5 → 6 → 7 → 8 → 9 → 1 → 2 → 3 → 4 → (back to 5)
```

**Example:** Year=5, Month=4, find Third
1. Put 4 in center (palace 5)
2. Everything shifts +1 in sequence
3. 5 moves from palace 5 → palace 6
4. Third = **6**

## Personal Cycles

### Personal Year
Where your **natal Year Ki** lands when the **global Year Ki** is in center.

Example: Natal 5 in global year 1
- Put 1 in center
- Where does 5 land? → Palace **9**
- Personal year = 9 (Fire)

### Personal Month
Where your **natal Year Ki** lands when the **global Month Ki** is in center.

Example: Natal 5 in global month 8
- Put 8 in center  
- Where does 5 land? → Palace **2**
- Personal month = 2 (Earth)

**Note:** Both personal year AND personal month use the natal YEAR Ki.

## Element Relationships

**Productive Cycle (feeds):**
Wood → Fire → Earth → Metal → Water → Wood

**Controlling Cycle (disciplines):**
Wood → Earth → Water → Fire → Metal → Wood

## Stella Tools

```bash
# Get natal Ki
npx mcporter call stella.get_ki birth_date=1986-05-01

# Get global Ki for a date
npx mcporter call stella.get_ki date=2026-02-05

# Get full profile with personal cycle
npx mcporter call stella.get_ki_cycle birth_date=1986-05-01
```

## Integration with I Ching

The 9 Ki trigrams map directly to I Ching trigrams. A reading can combine:
1. Natal Ki profile (who you are)
2. Personal cycle (where you are now)  
3. I Ching hexagram (specific guidance)

The trigrams in a cast hexagram can be interpreted through Ki lens for elemental synthesis.
