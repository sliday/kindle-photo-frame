package main

import (
	"encoding/json"
	"math/rand/v2"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Playlist walks the photo folder in the configured order and remembers its place on disk,
// so a restart neither repeats nor skips photos.
//
//	shuffle: every photo once in random order, then a fresh shuffle (default)
//	random:  any photo except the current one, repeats allowed
//	name:    file name order, wrapping around
type Playlist struct {
	dir, statePath, order string
	Deck                  []string `json:"deck"`
	Pos                   int      `json:"pos"`
	History               []string `json:"history"`
}

const historyMax = 50

func NewPlaylist(cfg Config) (*Playlist, error) {
	p := &Playlist{dir: cfg.PhotoDir, order: cfg.Order,
		statePath: filepath.Join(cfg.StateDir, "playlist-"+cfg.Order+".json")}
	if b, err := os.ReadFile(p.statePath); err == nil {
		_ = json.Unmarshal(b, p)
	}
	files, err := listPhotos(cfg.PhotoDir)
	if err != nil {
		return nil, err
	}
	if len(files) == 0 {
		return nil, os.ErrNotExist
	}
	if !sameSet(p.Deck, files) {
		p.rebuild(files)
	}
	return p, nil
}

func listPhotos(dir string) ([]string, error) {
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var out []string
	for _, e := range ents {
		n := e.Name()
		ext := strings.ToLower(filepath.Ext(n))
		if !e.IsDir() && !strings.HasPrefix(n, ".") && (ext == ".jpg" || ext == ".jpeg" || ext == ".png") {
			out = append(out, n)
		}
	}
	sort.Strings(out)
	return out, nil
}

func sameSet(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	seen := make(map[string]bool, len(a))
	for _, s := range a {
		seen[s] = true
	}
	for _, s := range b {
		if !seen[s] {
			return false
		}
	}
	return true
}

func (p *Playlist) rebuild(files []string) {
	p.Deck = append([]string(nil), files...)
	if p.order == "shuffle" {
		rand.Shuffle(len(p.Deck), func(i, j int) { p.Deck[i], p.Deck[j] = p.Deck[j], p.Deck[i] })
	}
	p.Pos = 0
}

// Current is the photo on screen.
func (p *Playlist) Current() string { return filepath.Join(p.dir, p.Deck[p.Pos%len(p.Deck)]) }

// Next advances and returns the new current photo.
func (p *Playlist) Next() string {
	p.History = append(p.History, p.Deck[p.Pos%len(p.Deck)])
	if len(p.History) > historyMax {
		p.History = p.History[len(p.History)-historyMax:]
	}
	switch p.order {
	case "random":
		if len(p.Deck) > 1 {
			n := rand.IntN(len(p.Deck) - 1)
			if n >= p.Pos {
				n++
			}
			p.Pos = n
		}
	case "shuffle":
		p.Pos++
		if p.Pos >= len(p.Deck) {
			last := p.Deck[len(p.Deck)-1]
			p.rebuild(p.Deck)
			// a fresh shuffle must not open with the photo just shown
			if len(p.Deck) > 1 && p.Deck[0] == last {
				p.Deck[0], p.Deck[1] = p.Deck[1], p.Deck[0]
			}
		}
	default:
		p.Pos = (p.Pos + 1) % len(p.Deck)
	}
	p.save()
	return p.Current()
}

// Prev steps back through what was shown, falling back to the previous deck slot.
func (p *Playlist) Prev() string {
	if n := len(p.History); n > 0 {
		name := p.History[n-1]
		p.History = p.History[:n-1]
		for i, s := range p.Deck {
			if s == name {
				p.Pos = i
				break
			}
		}
	} else {
		p.Pos = (p.Pos - 1 + len(p.Deck)) % len(p.Deck)
	}
	p.save()
	return p.Current()
}

func (p *Playlist) save() {
	b, _ := json.Marshal(p)
	_ = writeFileAtomic(p.statePath, b)
}
