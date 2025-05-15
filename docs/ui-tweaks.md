# UI Tweaks

## Fixed Header & Week Navigation

We have two fixed bars at the top of every page:

1. **Main Navbar**  
   - Selector: `.navbar`  
   - CSS:
     ```css
     position: fixed;
     top: 0;
     left: 0;
     width: 100%;
     z-index: 1055;
     ```

2. **Week Navigation Bar**  
   - Selector: `#week-nav`  
   - CSS:
     ```css
     position: fixed;
     top: 56px;             /* height of .navbar */
     left: 0;
     width: 100%;
     z-index: 1045;         /* below navbar */
     background: rgba(15,23,42,0.95);
     backdrop-filter: blur(4px);
     border-bottom: 1px solid #374151;
     padding: 8px 0;
     transition: top 0.3s ease-in-out;
     ```

3. **Content Spacing**  
   - Selectors: `#main-content`, `.container-fluid`  
   - CSS:
     ```css
     margin-top: calc(56px + 48px);  /* navbar + week-nav heights */
     ```

## Principles

- **Z‑index hierarchy** ensures dropdowns and menus layer correctly.  
- **Fixed positioning** keeps both bars visible when scrolling.  
- **Transparent background + blur** for modern frosted‑glass look.  
- **Transition** for smooth entrance on page load.