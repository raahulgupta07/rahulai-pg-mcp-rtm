<script lang="ts">
  let { type = "class-a", text = "" } = $props();

  const colorMap = {
    "class-a": "#007518",
    "class-b": "#ff9d00",
    "class-c": "#be2d06",
    "class-f4": "#006f7c",
    "grow": "#007518",
    "stable": "#ff9d00",
    "decline": "#be2d06",
    "risk-low": "#007518",
    "risk-med": "#ff9d00",
    "risk-high": "#be2d06",
  };

  let bg = $derived(colorMap[type] ?? "#383832");
</script>

<span
  class="inline-block px-2 font-black uppercase"
  style="
    background: {bg};
    color: white;
    font-size: 9px;
    padding-top: 2px;
    padding-bottom: 2px;
    border-radius: 0;
    font-family: 'Space Grotesk', sans-serif;
    line-height: 1.4;
  "
>
  {text}
</span>
