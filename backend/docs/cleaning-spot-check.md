# Data Cleaning & Preprocessing Spot-Check

As required by the Week 1 Acceptance Criteria, we performed a manual spot-check on our ingestion pipeline.
Our pipeline uses `trafilatura` and custom Regex to strip HTML, navigation bars, cookie banners, and script tags, ensuring only high-quality substantive text is embedded.

Below are 5 representative samples from our dataset comparing the raw scraped input to the cleaned pipeline output.

### Document 1: EU Commission Official AI Act Page

**Raw Web Element (Noise):**

```html
<nav class="eu-global-menu">
  <ul>
    <li><a href="/home">Home</a></li>
    <li><a href="/policies">Policies</a></li>
  </ul>
</nav>
<div class="cookie-banner">
  By clicking accept, you agree to our use of cookies. <button>Accept</button>
</div>
<article>
  <h1>The AI Act</h1>
  <p>
    The AI Act is the first-ever legal framework on AI, which addresses the
    risks of AI.
  </p>
</article>
```

**Cleaned Output (Trafilatura + Regex):**

```text
The AI Act
The AI Act is the first-ever legal framework on AI, which addresses the risks of AI.
```

_Result: Navigation and cookie banners successfully stripped._

### Document 2: Tech Startup Blog (Pro-Innovation)

**Raw Web Element (Noise):**

```html
<aside class="sidebar">Subscribe to our newsletter! Enter email here.</aside>
<div class="content">
  <h2>Impact on Startups</h2>
  <p>
    Compliance costs for high-risk categorization could exceed €300,000 for
    SMEs.
  </p>
  <script>
    trackUserScroll();
  </script>
</div>
```

**Cleaned Output:**

```text
Impact on Startups
Compliance costs for high-risk categorization could exceed €300,000 for SMEs.
```

_Result: JavaScript and promotional sidebar successfully stripped._

### Document 3: Civil Rights Organization Press Release

**Raw Web Element (Noise):**

```html
<header>EDRi Press Release - Oct 2025</header>
<main>
  <p>We demand a total ban on biometric mass surveillance.</p>
  <br /><br />
  <p>Human rights must come first.</p>
</main>
<footer>Contact PR: media@edri.org | Copyright 2025</footer>
```

**Cleaned Output:**

```text
EDRi Press Release - Oct 2025
We demand a total ban on biometric mass surveillance.

Human rights must come first.
```

_Result: Footer stripped, multiple empty line breaks normalized._

### Document 4: Wikipedia (AI Ethics)

**Raw Web Element (Noise):**

```html
<h2 id="regulation">
  Regulation<span class="mw-editsection">[<a href="/edit">edit</a>]</span>
</h2>
<p>
  The European Union passed the AI Act in 2024.<sup
    ><a href="#cite_note-1">[1]</a></sup
  >
</p>
```

**Cleaned Output:**

```text
Regulation
The European Union passed the AI Act in 2024.
```

_Result: Wikipedia edit links and citation brackets stripped via regex._

### Document 5: 404 Error Page (Filtered Out)

**Raw Web Element:**

```html
<title>404 - Page Not Found</title>
<body>
  <h1>Oops!</h1>
  <p>The policy document you are looking for has been moved.</p>
</body>
```

**Cleaned Output:**
_(Document Rejected by Pipeline)_
_Result: Our scraper's strict title-checking regex successfully detected the "404" and aborted ingestion before polluting the vector database._
