Use: `/review <scope>` -- dispatch the project's review lead for the given diff or scope.

Doctrine: this command serves the Review phase only; findings feed a separate Fix handoff, and Push stays with the operator. A plan review is a separate dispatch of the same lead against the spec (WL-15) and never a diff review.
