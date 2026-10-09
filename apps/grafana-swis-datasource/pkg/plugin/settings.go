package plugin

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
	_ "time/tzdata" // IANA zone names resolve on hosts without a zoneinfo database (Windows, scratch images)

	"github.com/grafana/grafana-plugin-sdk-go/backend"
)

// Settings is what the data source configuration page stores. Everything a user types
// lands in Grafana's jsonData except the two values that must never leave the server
// unencrypted: the Orion password and the CA bundle. Those come from secureJsonData,
// which Grafana encrypts at rest and never returns to the browser.
type Settings struct {
	Host          string `json:"host"`
	Port          int    `json:"port"`
	Username      string `json:"username"`
	TLSSkipVerify bool   `json:"tlsSkipVerify"`
	// TLSIgnoreHostname keeps chain verification against the pasted certificate but skips
	// the name check, for a pinned self-signed certificate whose names do not match the
	// host Grafana connects to. Unverified: OrionGuides documents that SWIS presents a
	// self-signed certificate, not which names it carries.
	TLSIgnoreHostname bool     `json:"tlsIgnoreHostname"`
	MaxRows           int      `json:"maxRows"`
	TimeoutSecs       int      `json:"timeoutSeconds"`
	InvokeAllow       []string `json:"invokeAllow"`

	// TimeBasis is the clock the plugin assumes for timestamps that carry no zone: the
	// bound $__timeFrom/$__timeTo values and zoneless DateTime values in results.
	// "utc" (the default) or "serverLocal". The schema does not declare a time basis for
	// System.DateTime (docs/swql/date-and-time.md), so this is an administrator's choice
	// made after measuring, not something the plugin can detect.
	TimeBasis string `json:"timeBasis"`
	// ServerTimeZone is an IANA zone name such as "America/Chicago", used with
	// "serverLocal". It follows daylight-saving changes; the fixed offset does not.
	ServerTimeZone string `json:"serverTimeZone"`
	// ServerUTCOffsetMinutes is a fixed offset east of UTC, used with "serverLocal" when
	// ServerTimeZone is empty. -300 is UTC-05:00.
	ServerUTCOffsetMinutes int `json:"serverUtcOffsetMinutes"`

	// Location is nil for the UTC basis, and the server's zone for "serverLocal".
	Location *time.Location `json:"-"`

	Password string `json:"-"`
	CACert   string `json:"-"`
}

const (
	timeBasisUTC         = "utc"
	timeBasisServerLocal = "serverLocal"
	maxOffsetMinutes     = 14 * 60
)

const (
	defaultPort    = 17774
	defaultMaxRows = 10000
	defaultTimeout = 60
)

// LoadSettings parses the instance settings and applies the platform defaults documented
// in OrionGuides: REST on 17774 from platform release 2023.1 onward, HTTPS only.
func LoadSettings(src backend.DataSourceInstanceSettings) (*Settings, error) {
	s := &Settings{}
	if len(src.JSONData) > 0 {
		if err := json.Unmarshal(src.JSONData, s); err != nil {
			return nil, fmt.Errorf("could not read data source settings: %w", err)
		}
	}
	s.Host = strings.TrimSpace(s.Host)
	s.Username = strings.TrimSpace(s.Username)
	if s.Port == 0 {
		s.Port = defaultPort
	}
	if s.MaxRows <= 0 {
		s.MaxRows = defaultMaxRows
	}
	if s.TimeoutSecs <= 0 {
		s.TimeoutSecs = defaultTimeout
	}
	cleaned := make([]string, 0, len(s.InvokeAllow))
	for _, v := range s.InvokeAllow {
		if v = strings.TrimSpace(v); v != "" {
			cleaned = append(cleaned, v)
		}
	}
	s.InvokeAllow = cleaned
	if err := s.resolveTimeBasis(); err != nil {
		return nil, err
	}
	s.Password = src.DecryptedSecureJSONData["password"]
	s.CACert = src.DecryptedSecureJSONData["caCert"]

	if s.Host == "" {
		return nil, fmt.Errorf("the Orion server host is not set")
	}
	if s.Username == "" {
		return nil, fmt.Errorf("the SWIS username is not set")
	}
	if s.Password == "" {
		return nil, fmt.Errorf("the SWIS password is not set")
	}
	return s, nil
}

// resolveTimeBasis validates the time-basis fields and sets Location.
func (s *Settings) resolveTimeBasis() error {
	s.ServerTimeZone = strings.TrimSpace(s.ServerTimeZone)
	switch s.TimeBasis {
	case "", timeBasisUTC:
		s.TimeBasis, s.Location = timeBasisUTC, nil
	case timeBasisServerLocal:
		if s.ServerTimeZone != "" {
			loc, err := time.LoadLocation(s.ServerTimeZone)
			if err != nil {
				return fmt.Errorf("the server time zone %q is not an IANA zone name: %w", s.ServerTimeZone, err)
			}
			s.Location = loc
			break
		}
		if s.ServerUTCOffsetMinutes < -maxOffsetMinutes || s.ServerUTCOffsetMinutes > maxOffsetMinutes {
			return fmt.Errorf("the server UTC offset must be between -%d and %d minutes, got %d", maxOffsetMinutes, maxOffsetMinutes, s.ServerUTCOffsetMinutes)
		}
		m, sign := s.ServerUTCOffsetMinutes, '+'
		if m < 0 {
			m, sign = -m, '-'
		}
		s.Location = time.FixedZone(fmt.Sprintf("UTC%c%02d:%02d", sign, m/60, m%60), s.ServerUTCOffsetMinutes*60)
	default:
		return fmt.Errorf("unknown time basis %q; use %q or %q", s.TimeBasis, timeBasisUTC, timeBasisServerLocal)
	}
	return nil
}

// InvokeAllowed reports whether Entity.Verb is on the allowlist. The comparison is exact
// and case sensitive because SWIS verb names are, and because an allowlist that matched
// loosely would be an allowlist that permitted more than the administrator wrote down.
func (s *Settings) InvokeAllowed(entity, verb string) bool {
	want := entity + "." + verb
	for _, v := range s.InvokeAllow {
		if v == want {
			return true
		}
	}
	return false
}
