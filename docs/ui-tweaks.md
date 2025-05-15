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

## Worker Page Adjustments

Worker pages receive additional margin to prevent layout overlap with the fixed navigation bars:

- **Worker Page Container**  
  - Selector: `body.worker-view .container > .row:first-child`  
  - CSS:
    ```css
    margin-top: 80px; /* Extra margin only for worker pages */
    ```

- **Worker Page Titles**  
  - Selector: `body.worker-view .page-title`  
  - CSS:
    ```css
    padding-top: 15px; /* Add padding to the top of page titles */
    ```

- **Worker Clock Page**  
  - Selector: `body.worker-view .container > div.clock-container`  
  - CSS:
    ```css
    margin-top: 80px; /* Special treatment for clock container */
    ```

## Implementation Strategy

1. The base template (`base.html`) adds the `worker-view` class to the body when the current user is a worker:
   ```html
   <body{% if current_user.is_authenticated and current_user.is_worker() %} class="worker-view"{% endif %}>
   ```

2. CSS selectors target this class to apply worker-specific spacing.

3. Different page structures require slightly different margin adjustments.

## Design Principles

- **Z‑index hierarchy** ensures dropdowns and menus layer correctly.  
- **Fixed positioning** keeps both bars visible when scrolling.  
- **Transparent background + blur** for modern frosted‑glass look.  
- **Transition** for smooth entrance on page load.
- **Role-based styling** handles layout differences for worker vs. admin/foreman interfaces.