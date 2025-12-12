# Export Functionality Test Checklist

**Date Created**: 2025-10-08
**Purpose**: Manual validation of enhanced PDF/DOCX exports

---

## Test Environment Setup

### Required Software
- [ ] Adobe Acrobat Reader (or Preview.app on macOS)
- [ ] Microsoft Word (or LibreOffice Writer)
- [ ] Web browser (for exports)

### Test Fixtures
- [ ] `baseline-current.md` - Complete test conversation
- [ ] Export from actual chat conversation with real content

---

## PDF Export Tests

### Links
- [ ] **Test 1**: Links are clickable (not plain text)
  - Open exported PDF in Adobe Reader
  - Click on links in the document
  - Verify links open in browser/external app
  - Expected: Links work, styled in blue

- [ ] **Test 2**: Multiple links on same line
  - Export content with 2+ links in one paragraph
  - Verify all links are clickable
  - Expected: All links function correctly

- [ ] **Test 3**: Relative vs absolute links
  - Test both `/docs/guide` and `https://example.com`
  - Expected: Both types preserved correctly

### Formatting
- [ ] **Test 4**: Headers hierarchy preserved
  - Export content with H1-H6 headers
  - Verify font sizes decrease appropriately
  - Expected: H1=16pt, H2=14pt, H3=12pt, etc.

- [ ] **Test 5**: Text wrapping
  - Export long paragraphs
  - Verify text wraps within margins
  - Expected: No text overflow, proper line breaks

- [ ] **Test 6**: Multi-page pagination
  - Export conversation >1 page
  - Verify page breaks occur properly
  - Expected: Text doesn't get cut off at page boundaries

### Mermaid Diagrams
- [ ] **Test 7**: Simple flowchart renders
  - Export conversation with basic Mermaid diagram
  - Verify diagram appears as image
  - Expected: Diagram visible, not code text

- [ ] **Test 8**: Complex diagram scales correctly
  - Export large sequence diagram
  - Verify image scales to fit page width
  - Expected: Diagram readable, aspect ratio preserved

- [ ] **Test 9**: Multiple diagrams
  - Export conversation with 3+ Mermaid diagrams
  - Verify all diagrams render
  - Expected: All diagrams present in correct order

- [ ] **Test 10**: Diagram failure handling
  - Export conversation with malformed Mermaid syntax
  - Verify error placeholder appears (red text)
  - Expected: `[Diagram rendering failed: ...]` message shown

- [ ] **Test 11**: Oversized diagram handling
  - If possible, create diagram >32000px
  - Verify graceful failure with error message
  - Expected: Placeholder text, no PDF corruption

### Edge Cases
- [ ] **Test 12**: Empty conversation
  - Export empty or very short content
  - Expected: Valid PDF created without errors

- [ ] **Test 13**: Special characters
  - Export content with ™ © € symbols
  - Expected: Symbols render or gracefully degrade

- [ ] **Test 14**: Emoji handling
  - Export content with emoji 😀 🚀
  - Check console for warning message
  - Expected: Warning logged, emoji may not render (acceptable)

---

## DOCX Export Tests

### Links
- [ ] **Test 15**: Links are clickable in Word
  - Open exported DOCX in MS Word
  - Ctrl+Click (or Cmd+Click) on links
  - Verify links open correctly
  - Expected: Links work as hyperlinks

- [ ] **Test 16**: Link styling
  - Verify links appear in blue, underlined
  - Expected: Standard hyperlink formatting

- [ ] **Test 17**: Link editing
  - Right-click link → Edit Hyperlink
  - Verify URL is correct
  - Expected: Links are real hyperlinks, not styled text

### Formatting
- [ ] **Test 18**: Headers use Word styles
  - Open DOCX in Word
  - Click on headers, check style dropdown
  - Expected: Headers use "Heading 1-6" styles (editable)

- [ ] **Test 19**: Text formatting preserved
  - Export content with bold, italic, inline code
  - Verify formatting intact
  - Expected: All formatting preserved

- [ ] **Test 20**: Document structure
  - Check Document Map / Navigation Pane
  - Expected: Headers appear in document outline

### Mermaid Diagrams
- [ ] **Test 21**: Diagrams embedded as images
  - Open DOCX, click on diagram
  - Verify it's an embedded image (not linked)
  - Expected: Image embedded in document

- [ ] **Test 22**: Image resizing
  - Click diagram, drag corner to resize
  - Verify aspect ratio maintained
  - Expected: Image resizes proportionally

- [ ] **Test 23**: Diagram quality
  - Export diagram, zoom in MS Word
  - Verify image is clear/sharp
  - Expected: PNG quality good at 100%+ zoom

- [ ] **Test 24**: Multiple diagrams in DOCX
  - Export conversation with 3+ diagrams
  - Verify all appear correctly
  - Expected: All diagrams embedded properly

### Compatibility
- [ ] **Test 25**: LibreOffice Writer
  - Open exported DOCX in LibreOffice Writer
  - Verify links, formatting, diagrams work
  - Expected: Compatible with open-source tools

- [ ] **Test 26**: Google Docs
  - Upload DOCX to Google Docs
  - Verify rendering is acceptable
  - Expected: Reasonably compatible

---

## Cross-Format Consistency Tests

- [ ] **Test 27**: Same content, different formats
  - Export same conversation as PDF and DOCX
  - Compare link placement, diagram order
  - Expected: Content identical across formats

- [ ] **Test 28**: Baseline comparison
  - Export `baseline-current.md` as PDF/DOCX
  - Compare to original markdown
  - Expected: All features from markdown present

---

## Stress Tests

### Performance
- [ ] **Test 29**: Large conversation (50 messages)
  - Export realistic 50-message conversation
  - Time the export process
  - Expected: Completes in <10 seconds

- [ ] **Test 30**: Many diagrams (10+ Mermaid)
  - Export conversation with 10 diagrams
  - Verify all render, no memory issues
  - Expected: Completes in <30 seconds, all diagrams present

### Error Recovery
- [ ] **Test 31**: Partial diagram failure
  - Export conversation with 3 diagrams, 1 malformed
  - Verify export completes with placeholder
  - Expected: Export succeeds, placeholder for failed diagram

- [ ] **Test 32**: All diagrams fail
  - Export conversation where all Mermaid is invalid
  - Verify export completes with placeholders
  - Expected: PDF/DOCX created with error placeholders

---

## Regression Tests

### Legacy Formats (Should Still Work)
- [ ] **Test 33**: TXT export unchanged
  - Export as TXT
  - Verify plain text output (no formatting)
  - Expected: Same behavior as before

- [ ] **Test 34**: MD export unchanged
  - Export as MD
  - Verify raw markdown preserved
  - Expected: Identical to source markdown

- [ ] **Test 35**: JSON export unchanged
  - Export as JSON
  - Verify structure intact
  - Expected: Valid JSON with expected fields

- [ ] **Test 36**: CSV/XLSX for tables
  - Export conversation with markdown table
  - Verify CSV/XLSX options appear
  - Expected: Table data exported correctly

---

## User Experience Tests

### Loading States
- [ ] **Test 37**: Download button shows status
  - Click PDF export, watch button text
  - Expected: Changes from "Download" to "Exporting..."

- [ ] **Test 38**: Button disabled during export
  - Click export, try clicking again immediately
  - Expected: Button disabled until export completes

### Error Messages
- [ ] **Test 39**: Meaningful error on failure
  - Force error (if possible)
  - Check error message displayed
  - Expected: Clear, actionable error message

---

## Summary Report

### PDF Export
- **Total Tests**: 14
- **Passed**: ___
- **Failed**: ___
- **Blocked**: ___

### DOCX Export
- **Total Tests**: 12
- **Passed**: ___
- **Failed**: ___
- **Blocked**: ___

### Other
- **Total Tests**: 13
- **Passed**: ___
- **Failed**: ___
- **Blocked**: ___

---

## Notes

### Issues Found
(Record any bugs, unexpected behavior, or areas for improvement)

---

### Recommendations
(Suggest improvements based on test results)

---

**Test Completed By**: _______________
**Date**: _______________
**Build/Commit**: _______________
