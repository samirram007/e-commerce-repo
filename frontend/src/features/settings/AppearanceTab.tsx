import { Button, Card, Field, Input } from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { useTheme } from "../../theme/theme-context";
import {
  ACCENT_SWATCHES,
  DENSITY_OPTIONS,
  THEME_OPTIONS,
  type Density,
  type ThemeMode,
} from "../../theme/theme-store";
import { cn } from "../../lib/utils";

const THEME_LABELS: Record<ThemeMode, { label: string; hint: string }> = {
  light: { label: "Light", hint: "Bright surfaces, highest legibility in daylight" },
  dark: { label: "Dark", hint: "Dark surfaces for low-light environments" },
  system: { label: "Follow system", hint: "Match the device appearance setting" },
};

const DENSITY_LABELS: Record<Density, string> = {
  compact: "Compact — denser rows and controls",
  comfortable: "Comfortable — default spacing",
};

export function AppearanceTab(): React.JSX.Element {
  const { theme, accentColor, density, setTheme, setAccentColor, setDensity, reset } = useTheme();

  const custom = accentColor && !ACCENT_SWATCHES.some((swatch) => swatch.value === accentColor);

  return (
    <>
      <Card title="Theme mode">
        <div className="grid-3">
          {THEME_OPTIONS.map((mode) => (
            <button
              key={mode}
              type="button"
              className={cn("theme-card", theme === mode && "selected")}
              aria-pressed={theme === mode}
              onClick={() => setTheme(mode)}
            >
              <div className="theme-card-preview" data-preview={mode}>
                <span className="theme-dot" />
                <span className="theme-dot muted-dot" />
              </div>
              <div>
                <strong>{THEME_LABELS[mode].label}</strong>
                <div className="muted">{THEME_LABELS[mode].hint}</div>
              </div>
            </button>
          ))}
        </div>
      </Card>

      <Card title="Accent color">
        <div className="accent-row">
          {ACCENT_SWATCHES.map((swatch) => (
            <button
              key={swatch.value}
              type="button"
              className={cn("accent-swatch", accentColor === swatch.value && "selected")}
              style={{ background: swatch.value }}
              title={swatch.label}
              aria-label={`${swatch.label} accent`}
              aria-pressed={accentColor === swatch.value}
              onClick={() => setAccentColor(swatch.value)}
            />
          ))}
          {custom ? (
            <span
              className="accent-swatch selected"
              style={{ background: accentColor }}
              title="Custom color"
            />
          ) : null}
        </div>
        <div className="grid-2" style={{ marginTop: 12 }}>
          <Field
            label="Custom hex color"
            hint="Optional — overrides the palette when set. Format: #RRGGBB."
          >
            <Input
              value={accentColor}
              placeholder="#RRGGBB"
              maxLength={7}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "" || /^#[0-9a-fA-F]{6}$/.test(next)) {
                setAccentColor(next);
              } else if (next.startsWith("#")) {
                setAccentColor(next.slice(0, 7).toUpperCase());
              }
            }}
            />
          </Field>
          <Field label="Reset">
            <Button variant="secondary" onClick={reset}>
              Restore defaults
            </Button>
          </Field>
        </div>
      </Card>

      <Card title="Density">
        <Field label="Control and table spacing">
          <SheetSelect
            value={density}
            options={DENSITY_OPTIONS.map((value) => ({ value, label: DENSITY_LABELS[value] }))}
            onChange={(value) => setDensity(value as Density)}
            title="Density"
          />
        </Field>
      </Card>
    </>
  );
}
