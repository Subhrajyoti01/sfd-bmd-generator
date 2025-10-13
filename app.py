from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

class Beam:
    # ... (The __init__, add_load, and _calculate_reactions methods are unchanged) ...
    def __init__(self, length, beam_type, supports):
        self.length = float(length)
        self.beam_type = beam_type
        self.supports = [float(s) for s in supports]
        self.loads = []
        self.reactions = {}

    def add_load(self, load_data):
        load_type = load_data.get('type')
        if load_type == 'udl' or load_type == 'uvl':
            if load_data['start'] >= load_data['end']:
                raise ValueError(f"For {load_type.upper()}, start position must be less than end position.")
        self.loads.append(load_data)

    def _calculate_reactions(self):
        if self.beam_type == "simply_supported" or self.beam_type == "overhang":
            if len(self.supports) != 2:
                raise ValueError("Simply supported or overhang beams require exactly two supports.")
            s1_pos, s2_pos = self.supports[0], self.supports[1]
            if s1_pos == s2_pos:
                raise ValueError("Supports cannot be at the same position.")
            
            sum_force_y = 0
            sum_moment_s1 = 0 
            
            for load in self.loads:
                if load['type'] == 'point':
                    P, a = load['magnitude'], load['position']
                    sum_force_y += P
                    sum_moment_s1 -= P * (a - s1_pos)
                elif load['type'] == 'udl':
                    w, start, end = load['magnitude'], load['start'], load['end']
                    eq_force = w * (end - start)
                    eq_pos = start + (end - start) / 2
                    sum_force_y += eq_force
                    sum_moment_s1 -= eq_force * (eq_pos - s1_pos)
                elif load['type'] == 'uvl':
                    w, start, end = load['magnitude'], load['start'], load['end']
                    length = end - start
                    eq_force = 0.5 * w * length
                    eq_pos = start + (2/3) * length
                    sum_force_y += eq_force
                    sum_moment_s1 -= eq_force * (eq_pos - s1_pos)
                elif load['type'] == 'moment':
                    sum_moment_s1 += load['magnitude']

            R2 = -sum_moment_s1 / (s2_pos - s1_pos)
            R1 = sum_force_y - R2
            self.reactions = {'R1': R1, 'R2': R2}

        elif self.beam_type == "cantilever":
            if len(self.supports) != 1:
                raise ValueError("Cantilever beams require exactly one fixed support.")
            fixed_pos = self.supports[0]
            
            sum_force_y = 0
            sum_moment_fixed = 0
            
            for load in self.loads:
                if load['type'] == 'point':
                    P, a = load['magnitude'], load['position']
                    sum_force_y += P
                    sum_moment_fixed += P * (a - fixed_pos)
                elif load['type'] == 'udl':
                    w, start, end = load['magnitude'], load['start'], load['end']
                    eq_force = w * (end - start)
                    eq_pos = start + (end - start) / 2
                    sum_force_y += eq_force
                    sum_moment_fixed += eq_force * (eq_pos - fixed_pos)
                elif load['type'] == 'uvl':
                    w, start, end = load['magnitude'], load['start'], load['end']
                    length = end - start
                    eq_force = 0.5 * w * length
                    eq_pos = start + (2/3) * length
                    sum_force_y += eq_force
                    sum_moment_fixed += eq_force * (eq_pos - fixed_pos)
                elif load['type'] == 'moment':
                    sum_moment_fixed -= load['magnitude']

            R_fixed = sum_force_y
            M_fixed = -sum_moment_fixed
            self.reactions = {'R_fixed': R_fixed, 'M_fixed': M_fixed}

    def calculate_diagrams(self):
        self._calculate_reactions()
        x_points, shear_forces, bending_moments = [], [], []
        num_steps = int(self.length * 200) + 1

        for i in range(num_steps):
            x = (i / 200.0)
            shear = 0
            moment = 0

            if self.beam_type == "simply_supported" or self.beam_type == "overhang":
                s1_pos, s2_pos = self.supports
                if x >= s1_pos: shear += self.reactions['R1']
                if x >= s2_pos: shear += self.reactions['R2']
                if x > s1_pos: moment += self.reactions['R1'] * (x - s1_pos)
                if x > s2_pos: moment += self.reactions['R2'] * (x - s2_pos)
            elif self.beam_type == "cantilever":
                fixed_pos = self.supports[0]
                if x >= fixed_pos: 
                    shear += self.reactions['R_fixed']
                    moment += self.reactions['M_fixed'] + self.reactions['R_fixed'] * (x - fixed_pos)

            for load in self.loads:
                if load['type'] == 'point':
                    if x >= load['position']:
                        shear -= load['magnitude']
                        moment -= load['magnitude'] * (x - load['position'])
                elif load['type'] == 'udl':
                    start, end, w = load['start'], load['end'], load['magnitude']
                    if x > start:
                        effective_end = min(x, end)
                        shear -= w * (effective_end - start)
                        moment -= 0.5 * w * (effective_end - start)**2
                elif load['type'] == 'uvl':
                    start, end, w = load['start'], load['end'], load['magnitude']
                    length = end - start
                    if x > start:
                        effective_x = min(x, end)
                        dist = effective_x - start
                        local_w = (w / length) * dist
                        shear -= 0.5 * local_w * dist
                        moment -= (w / (6 * length)) * dist**3
                elif load['type'] == 'moment':
                    if x >= load['position']:
                        moment += load['magnitude'] 

            x_points.append(round(x, 4))
            shear_forces.append(round(shear, 4))
            bending_moments.append(round(moment, 4))

        # --- NEW: CALCULATE MAX/MIN VALUES ---
        max_shear = max(shear_forces)
        min_shear = min(shear_forces)
        max_moment = max(bending_moments) # Max positive moment (sagging)
        min_moment = min(bending_moments) # Max negative moment (hogging)

        # Find the location of these values
        max_shear_pos = x_points[shear_forces.index(max_shear)]
        min_shear_pos = x_points[shear_forces.index(min_shear)]
        max_moment_pos = x_points[bending_moments.index(max_moment)]
        min_moment_pos = x_points[bending_moments.index(min_moment)]

        formatted_reactions = {k: round(v, 2) for k, v in self.reactions.items()}

        return {
            "x_points": x_points,
            "shear_forces": shear_forces,
            "bending_moments": bending_moments,
            "reactions": formatted_reactions,
            # --- NEW: SEND MAX/MIN DATA TO FRONTEND ---
            "summary": {
                "max_shear": {"value": round(max_shear, 2), "position": max_shear_pos},
                "min_shear": {"value": round(min_shear, 2), "position": min_shear_pos},
                "max_moment": {"value": round(max_moment, 2), "position": max_moment_pos},
                "min_moment": {"value": round(min_moment, 2), "position": min_moment_pos}
            }
        }

# ... (The @app.route('/calculate') and main block are unchanged) ...
@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        beam = Beam(data['beam_length'], data['beam_type'], data['supports'])
        for load in data['loads']:
            beam.add_load(load)
        
        result = beam.calculate_diagrams()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)