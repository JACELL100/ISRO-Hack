"""
A* Rover Traverse Path Planning Module
Plans optimal and safe rover path from landing site to target
doubly shadowed crater, considering terrain hazards and solar power.

Cost function components:
  1. Euclidean distance (base cost)
  2. Slope penalty (exponential beyond threshold)
  3. Roughness penalty
  4. Illumination / solar power constraint
  5. Crater/boulder hazard avoidance
  6. Proximity to PSR (minimize time in darkness)
"""
import numpy as np
import heapq
from typing import Dict, List, Tuple, Optional


def compute_cost_map(
    slope: np.ndarray,
    roughness: np.ndarray,
    shadow_map: np.ndarray,
    mean_illumination: np.ndarray,
    crater_mask: np.ndarray = None,
    boulder_density: np.ndarray = None,
    pixel_size_m: float = 30.0,
) -> np.ndarray:
    """
    Compute a per-pixel traversal cost map for the A* planner.
    Higher cost = more difficult / dangerous to traverse.
    """
    rows, cols = slope.shape

    # 1. Slope cost (steep exponential: strongly penalise >10° slopes)
    slope_cost = np.exp(np.clip(slope / 7.0, 0, 6)) - 1.0
    slope_cost = slope_cost / (slope_cost.max() + 1e-8)

    # 2. Roughness cost
    if roughness.max() > 0:
        roughness_cost = roughness / roughness.max()
    else:
        roughness_cost = np.zeros_like(roughness)

    # 3. Illumination cost (prefer illuminated regions for solar power)
    illum_cost = 1.0 - np.clip(mean_illumination, 0, 1)
    illum_cost[shadow_map == 1] = 0.5  # Mild penalty for PSR (no solar power)

    # 4. Hazard costs
    hazard_cost = np.zeros((rows, cols), dtype=np.float32)
    if crater_mask is not None:
        from scipy.ndimage import distance_transform_edt, binary_dilation
        danger = binary_dilation(crater_mask.astype(bool), iterations=3)
        hazard_cost += danger.astype(float) * 1.5

    if boulder_density is not None:
        hazard_cost += boulder_density * 1.0

    hazard_cost = np.clip(hazard_cost, 0, 3.0)

    # Impassable: slope > 25°
    impassable = slope > 25.0
    slope_cost[impassable] = 100.0

    # Weighted sum — slope is dominant
    cost = (
        0.50 * slope_cost
        + 0.20 * roughness_cost
        + 0.10 * illum_cost
        + 0.20 * hazard_cost
    )
    cost = cost + 0.05  # Base movement cost per pixel
    cost[impassable] = 1e6  # Barrier

    return cost.astype(np.float32)


def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Octile distance heuristic for 8-connectivity A*."""
    dr = abs(a[0] - b[0])
    dc = abs(a[1] - b[1])
    return max(dr, dc) + (np.sqrt(2) - 1) * min(dr, dc)


def astar(
    cost_map: np.ndarray,
    start: Tuple[int, int],
    goal: Tuple[int, int],
) -> Optional[List[Tuple[int, int]]]:
    """
    A* pathfinding on a 2D cost grid with 8-connectivity.

    Args:
        cost_map: Per-pixel traversal cost (higher = harder)
        start: (row, col) start position
        goal: (row, col) goal position

    Returns:
        List of (row, col) waypoints or None if no path found
    """
    rows, cols = cost_map.shape
    open_heap = []
    heapq.heappush(open_heap, (0.0, start))

    g_score = {start: 0.0}
    came_from: Dict[Tuple, Tuple] = {}
    closed_set = set()

    # 8-directional movement
    neighbors = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]
    diag_cost = np.sqrt(2)

    while open_heap:
        _, current = heapq.heappop(open_heap)

        if current in closed_set:
            continue
        closed_set.add(current)

        if current == goal:
            return _reconstruct_path(came_from, current)

        cr, cc = current
        for dr, dc in neighbors:
            nr, nc = cr + dr, cc + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if (nr, nc) in closed_set:
                continue

            move_cost = diag_cost if dr != 0 and dc != 0 else 1.0
            pixel_cost = cost_map[nr, nc]
            tentative_g = g_score[current] + move_cost * pixel_cost

            if tentative_g < g_score.get((nr, nc), np.inf):
                g_score[(nr, nc)] = tentative_g
                came_from[(nr, nc)] = current
                f = tentative_g + heuristic((nr, nc), goal)
                heapq.heappush(open_heap, (f, (nr, nc)))

    return None  # No path found


def _reconstruct_path(
    came_from: Dict, current: Tuple
) -> List[Tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def smooth_path(
    path: List[Tuple[int, int]], sigma: float = 3.0
) -> List[Tuple[int, int]]:
    """
    Apply Gaussian smoothing to the planned path for realistic rover motion.
    """
    if len(path) < 5:
        return path
    from scipy.ndimage import gaussian_filter1d
    rows = np.array([p[0] for p in path], dtype=float)
    cols = np.array([p[1] for p in path], dtype=float)
    rows_smooth = gaussian_filter1d(rows, sigma=sigma)
    cols_smooth = gaussian_filter1d(cols, sigma=sigma)
    return [(int(r), int(c)) for r, c in zip(rows_smooth, cols_smooth)]


def compute_path_metrics(
    path: List[Tuple[int, int]],
    cost_map: np.ndarray,
    slope: np.ndarray,
    dem: np.ndarray,
    pixel_size_m: float = 30.0,
) -> Dict:
    """
    Compute detailed metrics for the planned path.
    """
    if not path:
        return {"error": "No path found"}

    total_distance_m = 0.0
    total_cost = 0.0
    elevation_profile = []
    slope_profile = []
    max_slope = 0.0
    energy_consumption = 0.0  # Proxy in kJ

    for i, (r, c) in enumerate(path):
        elevation_profile.append(float(dem[r, c]))
        sl = float(slope[r, c])
        slope_profile.append(sl)
        max_slope = max(max_slope, sl)

        if i > 0:
            pr, pc = path[i - 1]
            dr = r - pr
            dc = c - pc
            step_dist = np.sqrt(dr**2 + dc**2) * pixel_size_m
            total_distance_m += step_dist
            total_cost += float(cost_map[r, c]) * step_dist / pixel_size_m
            # Energy: E ∝ distance × (1 + slope_factor)
            energy_consumption += step_dist * (1 + 0.5 * sl / 10.0)

    # Waypoints (every 10th point for display)
    step = max(1, len(path) // 30)
    waypoints = [{"row": r, "col": c} for r, c in path[::step]]

    # Elevation gain/loss
    elev = np.array(elevation_profile)
    elev_gain = float(np.sum(np.diff(elev)[np.diff(elev) > 0]))
    elev_loss = float(abs(np.sum(np.diff(elev)[np.diff(elev) < 0])))

    return {
        "total_distance_km": round(total_distance_m / 1000, 3),
        "total_cost": round(total_cost, 2),
        "max_slope_deg": round(max_slope, 2),
        "mean_slope_deg": round(float(np.mean(slope_profile)), 2),
        "elevation_gain_m": round(elev_gain, 1),
        "elevation_loss_m": round(elev_loss, 1),
        "estimated_energy_kJ": round(energy_consumption / 100, 2),
        "estimated_time_hours": round(total_distance_m / 1000 / 0.1, 1),  # 100m/hr rover
        "n_waypoints": len(path),
        "waypoints": waypoints,
        "elevation_profile": [round(e, 1) for e in elevation_profile[::step]],
        "slope_profile": [round(s, 2) for s in slope_profile[::step]],
        "path_safety": "SAFE" if max_slope < 15 else "CAUTION" if max_slope < 25 else "RISKY",
    }


def plan_rover_traverse(
    dem: np.ndarray,
    slope: np.ndarray,
    roughness: np.ndarray,
    shadow_map: np.ndarray,
    mean_illumination: np.ndarray,
    landing_site: Dict,
    target_crater: Dict,
    crater_mask: np.ndarray = None,
    boulder_density: np.ndarray = None,
    pixel_size_m: float = 30.0,
) -> Dict:
    """
    Full rover traverse planning pipeline.
    """
    # Build cost map
    cost_map = compute_cost_map(
        slope, roughness, shadow_map, mean_illumination,
        crater_mask, boulder_density, pixel_size_m
    )

    start = (landing_site["row"], landing_site["col"])
    goal = (target_crater["center_row"], target_crater["center_col"])

    # Validate start/goal bounds
    rows, cols = dem.shape
    start = (max(0, min(rows - 1, start[0])), max(0, min(cols - 1, start[1])))
    goal = (max(0, min(rows - 1, goal[0])), max(0, min(cols - 1, goal[1])))

    # Run A*
    raw_path = astar(cost_map, start, goal)

    if raw_path is None:
        return {
            "success": False,
            "error": "No traversable path found between landing site and target crater",
            "cost_map": cost_map,
        }

    # Smooth path
    smooth = smooth_path(raw_path, sigma=3.0)

    # Compute metrics
    metrics = compute_path_metrics(smooth, cost_map, slope, dem, pixel_size_m)

    return {
        "success": True,
        "path": [{"row": r, "col": c} for r, c in smooth],
        "raw_path": [{"row": r, "col": c} for r, c in raw_path[::5]],
        "cost_map": cost_map,
        "metrics": metrics,
        "start": {"row": start[0], "col": start[1]},
        "goal": {"row": goal[0], "col": goal[1]},
        "algorithm": "A* with terrain-aware cost function",
        "cost_components": {
            # Weights match compute_cost_map() exactly
            "slope_weight": 0.50,        # dominant — slope > 25° = impassable
            "roughness_weight": 0.20,
            "illumination_weight": 0.10, # solar power availability
            "hazard_weight": 0.20,       # crater rim + boulder avoidance
        },
    }
