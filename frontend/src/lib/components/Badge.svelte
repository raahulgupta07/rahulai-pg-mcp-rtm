<script lang="ts">
  let { type = "class-a", text = "" } = $props();

  const classMap: Record<string, string> = {
    "class-a": "badge-a",
    "class-b": "badge-b",
    "class-c": "badge-c",
    "class-f4": "badge-f4",
    "grow": "badge-a",
    "stable": "badge-b",
    "decline": "badge-c",
    "risk-low": "badge-a",
    "risk-med": "badge-b",
    "risk-high": "badge-c",
  };

  let cls = $derived(classMap[type] ?? "badge-neutral");
</script>

<span class="badge {cls}">{text}</span>
