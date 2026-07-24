# GitNexus MCP Tools Reference

Nine primary tools exposed by the GitNexus MCP server. All require a prior
`gitnexus analyze` run (writes `.gitnexus/`, registers in
`~/.gitnexus/registry.json`).

## query

Execution flows related to a concept. Returns process-grouped symbols.

```
query({search_query: "authentication"})
```

## context

360-degree symbol view: callers, callees, process membership.

```
context({name: "validateUser"})
```

## impact

Blast radius at depth 1/2/3 with confidence scores. Use before refactors
and in PR review.

```
impact({target: "validateUser", direction: "upstream", maxDepth: 3})
```

## trace

Shortest directed call path between two symbols. One call replaces chaining
3-8 `context`/`impact` hops.

```
trace({from: "processCheckout", to: "fetchRates"})
```

## detect_changes

Maps a git diff onto indexed symbols and affected flows. Cheaper than a full
re-analyze for review tasks.

```
detect_changes({scope: "staged"})
detect_changes({scope: "compare", base_ref: "main"})
```

## rename

Multi-file coordinated rename with confidence-tagged edits. Supports dry_run.

```
rename({symbol_name: "oldName", new_name: "newName", dry_run: true})
```

## cypher

Raw graph query when canned tools do not fit. Read
`gitnexus://repo/{name}/schema` first.

```
cypher({statement: "MATCH (c)-[:CodeRelation {type: 'CALLS'}]->(f:Function {name: 'X'}) RETURN c.name"})
```

## route_map

API route map: which components/hooks fetch which endpoints, and the handler
files that serve them.

```
route_map({repo: "my-app"})
```

## api_impact

Pre-change report for an API route: consumers, middleware, shape mismatches,
risk level.

```
api_impact({route: "/api/users", method: "GET"})
```
