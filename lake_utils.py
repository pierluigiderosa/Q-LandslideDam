# -*- coding: utf-8 -*-
"""
Funzioni numpy per il calcolo del lago di sbarramento a monte del cuneo.
Non dipendono da QGIS, così possono essere testate in modo indipendente.
"""
import numpy as np

try:
    from scipy import ndimage
except ImportError:  # scipy non presente in alcune installazioni di QGIS
    ndimage = None

# Connettività a 8 vicini, come r.lake
_STRUCTURE_8 = np.ones((3, 3), dtype=bool)
_NEIGHBOURS_8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]


def _dilate8(mask):
    """Dilatazione binaria a 8 vicini senza scipy."""
    padded = np.pad(mask, 1, mode='constant', constant_values=False)
    rows, cols = mask.shape
    out = np.zeros_like(mask)
    for dr in (0, 1, 2):
        for dc in (0, 1, 2):
            out |= padded[dr:dr + rows, dc:dc + cols]
    return out


def _border_mask(shape):
    border = np.zeros(shape, dtype=bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    return border


def connected_to(mask, seeds):
    """Celle di 'mask' connesse (8 vicini) ad almeno una delle celle 'seeds'."""
    seeds = seeds & mask
    if not np.any(seeds):
        return np.zeros_like(mask, dtype=bool)

    if ndimage is not None:
        labels, _ = ndimage.label(mask, structure=_STRUCTURE_8)
        return np.isin(labels, np.unique(labels[seeds]))

    # Fallback: crescita iterativa della regione per dilatazione
    region = seeds.copy()
    count = int(region.sum())
    while True:
        region = _dilate8(region) & mask
        new_count = int(region.sum())
        if new_count == count:
            return region
        count = new_count


def connected_region(mask, seed_rc):
    """Celle di 'mask' connesse (8 vicini) alla cella seed."""
    seeds = np.zeros_like(mask, dtype=bool)
    seeds[seed_rc] = True
    return connected_to(mask, seeds)


def dam_footprint(thickness_array):
    """Impronta del cuneo: componente principale delle celle con spessore > 0, senza buchi interni."""
    footprint = thickness_array > 0
    if not np.any(footprint):
        raise ValueError("Il cuneo non ha celle con spessore positivo.")
    start = np.unravel_index(np.argmax(thickness_array), thickness_array.shape)
    footprint = connected_region(footprint, start)
    outside = connected_to(~footprint, _border_mask(footprint.shape))
    return ~outside


def _ring_crossings(dem_array, ring):
    """
    Minimi del DEM lungo l'anello attorno al cuneo, ordinati per "persistenza".

    Il fiume attraversa l'anello due volte: l'uscita a valle è il punto più basso
    dell'anello, l'entrata a monte è il secondo minimo più marcato, cioè quello che
    si fonde con il bacino del minimo assoluto alla quota più alta (union-find in
    ordine di quota). Le piccole buche del DEM hanno persistenza bassa e vengono scartate.

    :returns: (outlet_rc, inlet_rc, persistenza_inlet)
    """
    rows, cols = dem_array.shape
    flat = dem_array.ravel()
    cells = np.flatnonzero(ring)
    order = cells[np.argsort(flat[cells], kind='stable')]

    parent = {}
    comp_min = {}
    comp_max = {}

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    best_cell, best_persistence = None, -1.0
    for p in order:
        p = int(p)
        z = float(flat[p])
        parent[p] = p
        comp_min[p] = p
        comp_max[p] = z
        r, c = divmod(p, cols)
        for dr, dc in _NEIGHBOURS_8:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < rows and 0 <= cc < cols):
                continue
            q = rr * cols + cc
            if q not in parent:
                continue
            ra, rb = find(p), find(q)
            if ra == rb:
                continue
            # Il bacino con il minimo più alto "muore" fondendosi con l'altro
            if flat[comp_min[ra]] <= flat[comp_min[rb]]:
                older, younger = ra, rb
            else:
                older, younger = rb, ra
            persistence = z - float(flat[comp_min[younger]])
            if persistence > best_persistence:
                best_persistence, best_cell = persistence, comp_min[younger]
            parent[younger] = older
            comp_max[older] = z
        comp_max[find(p)] = z

    # Anello spezzato (bordo del DEM o NoData): i tratti mai fusi contano con la loro escursione
    outlet = int(order[0])
    global_root = find(outlet)
    for root in {find(p) for p in parent}:
        if root == global_root:
            continue
        persistence = comp_max[root] - float(flat[comp_min[root]])
        if persistence > best_persistence:
            best_persistence, best_cell = persistence, comp_min[root]

    if best_cell is None:
        raise ValueError("Impossibile individuare l'alveo a monte attorno al cuneo.")
    return divmod(outlet, cols), divmod(best_cell, cols), best_persistence


def find_seed_and_outlet(dem_array, thickness_array, ring_cells=3):
    """
    Individua il seed point a monte e il punto di riferimento a valle lungo un anello
    di 'ring_cells' celle attorno all'impronta del cuneo, usando il DEM ante-frana.
    Non dipende dalla convenzione con cui è definita la direzione del cuneo.

    :returns: (seed_rc, outlet_rc, persistenza)
    """
    footprint = dam_footprint(thickness_array)
    ring = footprint
    for _ in range(ring_cells):
        ring = _dilate8(ring)
    ring &= ~footprint & ~np.isnan(dem_array)
    if not np.any(ring):
        raise ValueError("Nessuna cella valida del DEM attorno al cuneo.")

    outlet_rc, inlet_rc, persistence = _ring_crossings(dem_array, ring)
    return tuple(int(v) for v in inlet_rc), tuple(int(v) for v in outlet_rc), persistence


def compute_spill_level(modified_dem, seed_rc, outlet_rc, max_level, tolerance=0.01):
    """
    Quota di sfioro per bisezione: la quota più alta per cui l'acqua che sale
    dal seed non raggiunge il punto a valle né l'uscita dal dominio (bordo del DEM
    o NoData collegati al bordo). I buchi NoData interni non sono considerati uscite.

    :returns: dict con
        'level'      quota di sfioro
        'lake_mask'  celle del lago
        'status'     'ok' (sfioro verso valle), 'border' (sfioro verso il bordo del DEM,
                     lago troncato), 'not_effective' (lo sbarramento non chiude la valle)
        'exit_rc'    cella da cui l'acqua esce appena sopra la quota di sfioro
        'internal_nodata_cells' numero di celle NoData interne al DEM
    """
    valid = ~np.isnan(modified_dem)
    border = _border_mask(valid.shape)
    exterior_nodata = connected_to(~valid, border)
    edge = (border | _dilate8(exterior_nodata)) & valid
    internal_nodata = int(np.count_nonzero(~valid & ~exterior_nodata))

    def flooded(level):
        return connected_region(valid & (modified_dem <= level), seed_rc)

    def exit_cell(region):
        if region[outlet_rc]:
            return tuple(outlet_rc)
        hits = region & edge
        if np.any(hits):
            flat_index = np.argmin(np.where(hits, modified_dem, np.inf))
            return tuple(int(v) for v in np.unravel_index(flat_index, modified_dem.shape))
        return None

    low = float(modified_dem[seed_rc])
    high = float(max_level)
    result = {'internal_nodata_cells': internal_nodata}

    exit_low = exit_cell(flooded(low))
    if exit_low is not None:
        result.update(level=low, lake_mask=np.zeros_like(valid), status='not_effective', exit_rc=exit_low)
        return result

    region_high = flooded(high)
    if exit_cell(region_high) is None:
        result.update(level=high, lake_mask=region_high, status='ok', exit_rc=None)
        return result

    while high - low > tolerance:
        mid = 0.5 * (low + high)
        if exit_cell(flooded(mid)) is not None:
            high = mid
        else:
            low = mid

    exit_high = exit_cell(flooded(high))
    status = 'ok' if exit_high == tuple(outlet_rc) else 'border'
    result.update(level=low, lake_mask=flooded(low), status=status, exit_rc=exit_high)
    return result


def lake_statistics(modified_dem, lake_mask, level, cell_area):
    """Profondità, volume (m³), area (m²) e profondità massima del lago."""
    depth = np.where(lake_mask, level - modified_dem, np.nan)
    depth = np.where(depth > 0, depth, np.nan)
    wet = ~np.isnan(depth)
    volume = float(np.nansum(depth)) * cell_area
    area = float(np.count_nonzero(wet)) * cell_area
    max_depth = float(np.nanmax(depth)) if np.any(wet) else 0.0
    return depth, volume, area, max_depth
