from breedgraph.adapters.pmtiles import region_cells, region_geojson, cells_bounds


def test_a_location_well_inside_a_cell_needs_that_cell():
    # Galway, more than 25 km from the edges of the cell 53-54 N, 10-9 W
    assert region_cells([(53.5, -9.5)]) == {(143, 170)}


def test_a_location_near_an_edge_takes_the_neighbouring_cell():
    assert region_cells([(53.05, -9.5)]) == {(142, 170), (143, 170)}
    # near a corner, the three neighbours too
    assert region_cells([(53.05, -9.95)]) == {(142, 169), (142, 170), (143, 169), (143, 170)}


def test_coordinates_combine_and_missing_ones_are_skipped():
    assert region_cells([(53.5, -9.5), (53.6, -9.4), (None, 1.0)]) == {(143, 170)}
    assert region_cells([]) == set()


def test_geojson_and_bounds():
    cells = {(143, 170), (142, 170)}
    geojson = region_geojson(cells)
    assert geojson['type'] == 'MultiPolygon'
    assert geojson['coordinates'][1] == [[[-10, 53], [-9, 53], [-9, 54], [-10, 54], [-10, 53]]]
    assert cells_bounds(cells) == [[52, -10], [54, -9]]
    assert cells_bounds(set()) is None


def test_cells_stay_within_the_map():
    cells = region_cells([(89.0, 179.9)], padding_km=50)
    assert all(0 <= column < 360 for _, column in cells)
    [[south, _], [north, _]] = cells_bounds(cells)
    assert north <= 85.05
