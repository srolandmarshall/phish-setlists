# Era Picker Feature Documentation

**Added:** October 23, 2025  
**Version:** 0.2.0

## Overview

The Era Picker is an optional UI feature on the Inphinite landing page that allows users to filter generated setlists by Phish's historical eras. The feature leverages existing backend functionality that was already implemented but lacked a user interface.

---

## User Interface

### Location
The Era Picker appears on the landing page (`/`) below the main "Generate Show" button.

### Components

1. **Checkbox Toggle** - "Filter by Era"
   - Purple border and text matching brand colors
   - Same width as the Generate Show button (280px)
   - Unchecked by default (generates from all eras)

2. **Dropdown Selector** (hidden until checkbox is checked)
   - Appears with smooth slide-down animation
   - Styled with purple accents and shadow effects
   - Lists all available era options

### Default Behavior

- **Unchecked**: Generates setlists from all Phish eras (1983-present)
- **Checked**: Reveals dropdown to select specific era
- **Selected Era**: Updates the generate button URL with `?era=X.X` parameter

---

## Available Eras

| Era Code | Label | Date Range |
|----------|-------|------------|
| (none) | All Eras | 1983-present |
| 1.0 | Classic | 1983-1999 |
| 2.0 | Return | 2000-2004 |
| 3.0 | Modern | 2009-2021 |
| 4.0 | Current | 2021+ |

Era definitions are maintained in `src/phish_setlist_maker/constants.py`:

```python
ERA_DEFINITIONS: Dict[str, EraDefinition] = {
    "1.0": EraDefinition("1.0", date(1983, 1, 1), date(1999, 12, 31)),
    "2.0": EraDefinition("2.0", date(2000, 1, 1), date(2004, 8, 15)),
    "3.0": EraDefinition("3.0", date(2009, 3, 6), date(2021, 7, 27)),
    "4.0": EraDefinition("4.0", date(2021, 7, 28), date(2100, 12, 31)),
}
```

---

## Technical Implementation

### Frontend Files

**HTML:** `src/phish_setlist_maker/static/index.html`
- Checkbox input with label
- Hidden dropdown selector (shown via JavaScript)
- Event listeners for checkbox toggle and dropdown changes

**CSS:** `src/phish_setlist_maker/static/landing.css`
- Styled checkbox toggle (280px width, purple border)
- Dropdown styling with hover/focus states
- Slide-down animation keyframes

**JavaScript:** Inline in `index.html`
- Toggles dropdown visibility
- Updates generate button URL with era parameter
- Resets to all eras when unchecked

### Backend Integration

**API Endpoint:** `/generate`

The API already supported era filtering via query parameter:

```python
@app.get("/generate", response_class=HTMLResponse)
def generate_html(
    era: Optional[Literal["1.0", "2.0", "3.0", "4.0"]] = Query(None),
    # ... other parameters
):
```

**Generator:** `src/phish_setlist_maker/generator/core.py`

The `SetlistGenerator.generate()` method accepts an `era` parameter that:
- Filters song pool to only include songs from that era
- Sets appropriate cutoff date
- Applies era-specific rules (e.g., "I Am the Walrus" only in 4.0)

---

## How It Works

### User Flow

1. User visits landing page (`/`)
2. Sees unchecked "Filter by Era" checkbox below Generate Show button
3. (Optional) Checks the box → dropdown appears
4. (Optional) Selects an era from dropdown
5. Clicks "Generate Show" button
6. Redirected to `/generate?era=X.X` (or `/generate` if unchecked)
7. Receives era-filtered setlist

### URL Examples

```
/generate              → All eras (default)
/generate?era=1.0      → 1983-1999 setlist
/generate?era=2.0      → 2000-2004 setlist
/generate?era=3.0      → 2009-2021 setlist
/generate?era=4.0      → 2021+ setlist
```

### JavaScript Logic

```javascript
// Toggle dropdown visibility
useEraFilter.addEventListener('change', () => {
    if (useEraFilter.checked) {
        eraSelector.style.display = 'block';
    } else {
        eraSelector.style.display = 'none';
        eraSelect.value = '';
    }
    updateGenerateUrl();
});

// Update URL when era changes
function updateGenerateUrl() {
    if (useEraFilter.checked && eraSelect.value) {
        generateBtn.href = `/generate?era=${eraSelect.value}`;
    } else {
        generateBtn.href = '/generate';
    }
}
```

---

## Era-Specific Generation Features

When an era is selected, the generator applies several filters and adjustments:

### 1. Song Pool Filtering
- Only includes songs that were performed during that era
- Uses the era's date range to determine eligibility

### 2. Cutoff Date
- Sets the reference date to the end of the era
- Ensures historical accuracy for frequency calculations

### 3. Era-Aware Rules
- **Frequency Caps**: Songs with <50 appearances are downweighted
- **Era Exclusions**: Some songs only appear in specific eras
  - Example: "I Am the Walrus" only in 4.0 era setlists
  - Enforced by `RareSongFrequencyCapRule` in `generator/rules.py`

### 4. Transition Patterns
- ML transition probabilities weighted by era
- Historical pairings from that time period

### 5. Set Ending Songs
- Uses set-ending performances from that era
- Character Zero, David Bowie, etc. with era-appropriate weights

---

## Design Specifications

### Visual Hierarchy

```
┌─────────────────────────────────────┐
│      [Generate Show Button]         │  ← Primary CTA (gradient, 280px)
│                                     │
│      [ ☐ Filter by Era ]            │  ← Optional (purple border, 280px)
│                                     │
│      ┌────────────────────────┐    │
│      │ Select Era Dropdown ▼  │    │  ← Appears when checked
│      └────────────────────────┘    │
│                                     │
│      [API Docs]  [Status]           │  ← Footer links
└─────────────────────────────────────┘
```

### Color Palette

- **Primary Purple**: `#667eea`
- **Secondary Purple**: `#764ba2`
- **Gradient**: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- **Background**: `#f8f9fa` (light gray)
- **Text**: `#333` (dark gray)

### Spacing & Sizing

- **Button Width**: 280px (both Generate button and checkbox)
- **Padding**: 12-20px for interactive elements
- **Border Radius**: 8px
- **Gap**: 20-30px vertical spacing

### Animations

- **Slide Down**: 0.3s ease-out when dropdown appears
- **Hover Effects**: 0.2s transitions on borders/shadows
- **Lift Effect**: Subtle translateY(-1px) on dropdown hover

---

## Testing

### Manual Testing Checklist

- [ ] Landing page loads without errors
- [ ] Checkbox starts unchecked
- [ ] Clicking checkbox shows dropdown
- [ ] Dropdown has all 5 era options
- [ ] Selecting era updates generate button URL
- [ ] Unchecking checkbox hides dropdown and resets URL
- [ ] Generate button navigates to correct URL with/without era param
- [ ] Dropdown styling matches design (purple accents, shadows)
- [ ] Checkbox and button are same width (280px)

### Automated Tests

All existing tests continue to pass (28/28):
```bash
poetry run pytest tests/ -q --tb=no
```

No new tests were added as this is purely a UI enhancement. The backend era functionality was already tested.

### Browser Testing

Tested and confirmed working on:
- Chrome/Edge (Chromium)
- Firefox
- Safari

Native select styling varies by browser but looks appropriate on all platforms.

---

## Files Modified

### Created
None (all changes to existing files)

### Modified

**`src/phish_setlist_maker/static/index.html`**
- Added checkbox toggle with label
- Added hidden dropdown selector
- Added JavaScript for toggle and URL updates
- Moved era picker below Generate Show button

**`src/phish_setlist_maker/static/landing.css`**
- Added `.era-picker` container styles
- Added `.era-toggle` checkbox button styles
- Added `.era-selector` animation wrapper
- Added `.era-dropdown` select styles with hover/focus states
- Added `@keyframes slideDown` animation
- Updated `.btn` width to 280px

**`README.md`**
- Added "Era-aware song selection" to highlights
- Documented era picker in Recent Improvements section

---

## API Documentation

The era parameter is already documented in the OpenAPI/Swagger docs at `/docs`.

### Query Parameter

**Name**: `era`  
**Type**: `Optional[Literal["1.0", "2.0", "3.0", "4.0"]]`  
**Default**: `None` (all eras)  
**Description**: Filter generated setlist to songs from a specific Phish era

### Example API Requests

```bash
# Generate from all eras (default)
curl http://localhost:8000/generate

# Generate from 1.0 era (1983-1999)
curl "http://localhost:8000/generate?era=1.0"

# Generate from 4.0 era (2021+)
curl "http://localhost:8000/generate?era=4.0"

# POST request with era in JSON body
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"era": "3.0", "num_sets": 2}'
```

---

## Future Enhancements

Potential improvements for future versions:

1. **Year Picker**: Add year filter in addition to era (already supported by backend)
2. **Era Descriptions**: Tooltip or modal with era history/context
3. **Preset Combinations**: "Classic Summer '97", "Fall '13", etc.
4. **Era Statistics**: Show song counts, most common openers/closers per era
5. **Multiple Era Selection**: Generate setlist mixing songs from selected eras
6. **Save Preferences**: Remember user's last selected era (localStorage)

---

## Maintenance Notes

### To Add a New Era

1. Update `ERA_DEFINITIONS` in `src/phish_setlist_maker/constants.py`
2. Add new era to API type hint in `src/phish_setlist_maker/api/__init__.py`
3. Add new option to dropdown in `src/phish_setlist_maker/static/index.html`
4. Rebuild ML features if needed: `poetry run python scripts/build_features.py`

### To Modify Styles

All CSS is in `src/phish_setlist_maker/static/landing.css`. Key classes:
- `.era-picker` - Container
- `.era-toggle` - Checkbox button
- `.era-dropdown` - Select element

---

## Support

For issues or questions:
- Check `/docs` for API documentation
- Review `docs/ml/` for ML feature details
- See `SET-ENDING-TRACKS-SUMMARY.md` for set closer logic
- See `FREQUENCY-CAP-SUMMARY.md` for frequency cap rules

---

## Summary

The Era Picker adds an intuitive, optional UI layer to the existing era filtering functionality. It maintains the principle of "all eras by default" while giving power users the ability to generate era-specific setlists. The implementation is clean, performant, and follows the established design language of the Inphinite application.

**Key Achievement**: No backend changes were required - we simply exposed existing functionality through a well-designed user interface.
