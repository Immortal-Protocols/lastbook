# Checked source comparisons

The optional `content/source-disagreements.json` file holds editorial comparisons backed by original library pages. Each record identifies exact document IDs, page numbers and required quotations. A `notice` is shown to the reader when the question falls within the comparison and the application verifies all required quotations on the original pages.

Use the `scope` object to describe when a comparison applies. Its `subject` and `intent` are case-insensitive regular expressions. Both must match the current user question. An optional `exclude` expression rules out a specific incompatible audience or intent. A record with missing or invalid scope remains inert. Keep scopes focused on stable subject and intent terms so they work with ordinary paraphrases, including a question that also asks about another topic.

The optional `finding` helps the assistant apply page conditions and distinguish the scope of each source. It is appended after the original evidence and appears in the model prompt only while complete original pages for all referenced citations are present. A search excerpt or an editorial finding contributes no additional citation eligibility. The independent notice may still link its verified pages for the reader to inspect when a page does not fit in the prompt.

Review the original pages and the proposed notice together before shipping a comparison. Run the source evidence and packaging fixtures after updating the file.
